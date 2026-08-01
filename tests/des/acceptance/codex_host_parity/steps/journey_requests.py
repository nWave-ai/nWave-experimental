"""Slice-01 chain vocabulary and the one service the step methods invoke.

Mandate-12 SSOT: the acceptance vocabulary is a type (:class:`ChainLink`,
:class:`CandidateIdentity`), the request assembly, the assembled-surface
sequence and the driving call live in one service
(:class:`InstalledParityJourney`), and step methods only invoke that service.

Three disciplines this module exists to make structural rather than
conventional:

1. **Assembled surface.** The walking skeleton does NOT execute the checkout.
   It mints a candidate through the real producer, installs it into a CLEAN
   prefix, and then runs the INSTALLED entry from outside the source tree with
   a scrubbed environment. Proving that the source tree works is not the claim
   this feature makes.
2. **No literal identity anywhere.** The candidate every crossing must quote is
   the value the PRODUCER RETURNS for build inputs this run invented seconds
   earlier. There is no published-candidate constant in this file to hard-code
   against: an implementation that answers with a fixed digest fails on the
   first run, and the crossing set must match the declared chain EXACTLY --
   neither missing nor extra.
3. **Every oracle reads an external fact.** Each promise is settled by
   something the producer cannot narrate: a token proved unique across the
   installed tree, an obligation the installed role itself declares and a file
   that must then exist, a native Codex lifecycle event fired from the
   registration the install wrote, a loop id echoed by a durable attestation,
   the provenance of the executed file cross-checked on disk, and the
   catalogue's private paths measured against the real install inventory.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import subprocess
import sys
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from ..composition import CodexParityJourneyComposition
from ..composition import field as public_field
from ..port_witnesses import FivePortWitnesses
from .native_codex_host import NativeCodexHost, NativeHostObservation


# A candidate and a machine that are deliberately NOT the ones under test.
FOREIGN_CANDIDATE = "0" * 64
FOREIGN_COMPOSITION = "codex-cli-macos-native"

# What a user-site decoy writes if the installed entry ever imports it. Its
# absence is the observation; its presence would mean the clean process
# accepted a package from the user's own site rather than the candidate's.
DECOY_MARKER = "user-site-decoy-was-imported"

# The native lifecycle event a Codex user's forbidden action raises. Native
# Codex vocabulary, not nWave's. The TOOL it arrives under is never assumed:
# the real host advertises what it supports and the boot drives that.
NATIVE_LIFECYCLE_EVENT = "PreToolUse"

# Shortest line the installed material may offer as a discriminating marker.
_MIN_TOKEN_LENGTH = 24

#: A policy line that GRANTS something: a named field with a value.
_GRANT_FIELD = re.compile(r"^(?P<field>[A-Za-z_][A-Za-z0-9_.\-]*)\s*=\s*(?P<value>.+)$")

#: The one role this journey runs, and the declarations it owns.
SELECTED_ROLE = "specialist"
_ROLE_DECLARATION_KEYS = (
    "observable-obligation",
    "requires-approval",
    "guarded-effect",
)


class ChainLink(str, Enum):
    """One user-visible crossing of the installed vertical."""

    SPECIALIST_FOLLOWS_INSTRUCTIONS = "role:specialist-follows-instructions"
    SPECIALIST_READS_ITS_EXPERTISE = "skill:specialist-reads-installed-expertise"
    SPECIALIST_READS_PROJECT_RULE = "rule:project-durable-instruction"
    APPROVAL_IS_ENFORCED_OR_REFUSED = "policy:approval-requirement"
    SAFEGUARD_REACTS = "hook:workflow-safeguard-reacts"
    LOOP_TICK_IS_ATTESTED = "loop:manual-tick-attested"
    CLAUDE_USER_IS_UNCHANGED = "preservation:claude-user-unchanged"


#: The crossings a Codex user exercises. Claude preservation is a floor of the
#: same journey but is not a capability the Codex user invokes.
CODEX_CROSSINGS = tuple(
    link for link in ChainLink if link is not ChainLink.CLAUDE_USER_IS_UNCHANGED
)


@dataclass(frozen=True)
class BuildInputs:
    """The three inputs the candidate's identity is minted from.

    Invented per run, so no expected identity can be written down in advance
    and no implementation can satisfy this suite with a constant.
    """

    distribution_digest: str
    public_manifest_digest: str
    build_recipe_version: str

    @classmethod
    def for_this_run(cls) -> BuildInputs:
        run = uuid.uuid4().hex
        return cls(
            distribution_digest=f"distribution-{run}",
            public_manifest_digest=f"manifest-{run}",
            build_recipe_version=f"recipe-{run}",
        )

    def as_public(self) -> dict[str, str]:
        return {
            "distribution_digest": self.distribution_digest,
            "public_manifest_digest": self.public_manifest_digest,
            "build_recipe_version": self.build_recipe_version,
        }

    def as_published(self) -> dict[str, str]:
        """What the TEST may declare about a real build: not its bytes.

        The distribution digest belongs to the artifact the producer actually
        assembles, so the test does not supply one -- it weighs the result
        instead. Supplying it would let the producer be checked against a
        number the test made up.
        """
        return {
            "public_manifest_digest": self.public_manifest_digest,
            "build_recipe_version": self.build_recipe_version,
        }

    def as_other_published(self) -> dict[str, str]:
        """Publishable inputs for a MATERIALLY different second build."""
        return {
            "public_manifest_digest": f"{self.public_manifest_digest}-second",
            "build_recipe_version": f"{self.build_recipe_version}-second",
        }

    def with_other_bytes(self) -> dict[str, str]:
        """The same build, from DIFFERENT distribution bytes.

        The second observation of the metamorphic pair: whatever identity the
        first set mints, this one must mint a different one.
        """
        return {
            **self.as_public(),
            "distribution_digest": f"{self.distribution_digest}-other",
        }


@dataclass(frozen=True)
class CandidateIdentity:
    """The tuple every crossing receipt must quote to be counted."""

    candidate: str
    composition: str

    def as_pair(self) -> tuple[str, str]:
        return (self.candidate, self.composition)


@dataclass(frozen=True)
class CrossingReceipt:
    """One structured crossing observation read off the public result."""

    item: str
    verdict: str
    identity: tuple[str, str]
    external_effect_count: int

    @classmethod
    def read(cls, record: object) -> CrossingReceipt:
        return cls(
            item=str(public_field(record, "item")),
            verdict=str(public_field(record, "verdict")),
            identity=(
                str(public_field(record, "candidate_id")),
                str(public_field(record, "host_composition_id")),
            ),
            external_effect_count=int(public_field(record, "external_effect_count")),
        )


@dataclass
class PublishedJourneyRun:
    """What the user can observe after driving the journey once."""

    result: Any = None
    ports: FivePortWitnesses | None = None
    identity: CandidateIdentity = field(
        default_factory=lambda: CandidateIdentity("", "")
    )

    def observable(self, name: str) -> object:
        return public_field(self.result, name)

    def outcome(self) -> str:
        return str(self.observable("outcome"))

    def remedy_text(self) -> str:
        """The full WHAT/WHY/HOW the user is shown, as one searchable string."""
        diagnostic = self.observable("diagnostic")
        return " ".join(
            str(public_field(diagnostic, part)) for part in ("what", "why", "how")
        )

    def crossings(self) -> tuple[CrossingReceipt, ...]:
        """Every structured crossing receipt the journey reported."""
        return tuple(
            CrossingReceipt.read(record) for record in self.observable("crossings")
        )

    def crossing_items(self) -> tuple[str, ...]:
        """Every reported crossing, WITH its multiplicity.

        A set cannot tell one walk of the chain from three: duplicates
        collapse and a chain walked twice reads as a chain walked once. The
        multiset is what the comparison needs.
        """
        return tuple(sorted(receipt.item for receipt in self.crossings()))

    def crossing(self, link: ChainLink) -> CrossingReceipt | None:
        for receipt in self.crossings():
            if receipt.item == link.value:
                return receipt
        return None

    def claude_surface_before(self) -> str:
        """The Claude user's surface as production observed it BEFORE deploying."""
        return str(self.observable("claude_surface_before"))

    def claude_surface_after(self) -> str:
        """The same surface as production observed it AFTER deploying."""
        return str(self.observable("claude_surface_after"))

    def owned_material(self) -> str:
        """What nWave owns on this machine after the install."""
        return str(self.observable("owned_material"))


@dataclass(frozen=True)
class InstalledProvenance:
    """Where the clean process says its own code came from.

    A report, therefore never trusted alone: every path here is cross-checked
    against the filesystem by :class:`ObservedJourney`, resolved through
    symlinks, and required to exist under the prefix.
    """

    executable: Path
    module_file: Path
    import_roots: tuple[Path, ...]

    @classmethod
    def read(cls, payload: dict[str, Any]) -> InstalledProvenance | None:
        record = payload.get("provenance")
        if not isinstance(record, dict):
            return None
        return cls(
            executable=Path(str(record.get("executable", ""))),
            module_file=Path(str(record.get("module_file", ""))),
            import_roots=tuple(
                Path(str(root)) for root in record.get("import_roots", ()) or ()
            ),
        )

    def every_path(self) -> tuple[Path, ...]:
        return (self.executable, self.module_file, *self.import_roots)


@dataclass(frozen=True)
class ObservedJourney:
    """Effects the ACCEPTANCE TEST observed on the clean machine.

    Every field here is measured by the test against the workspace, the
    installed prefix, a native lifecycle invocation or an exit code -- NEVER
    parsed out of the journey's own report, with the two declared exceptions of
    the identity binding and the self-reported provenance, and the second of
    those is cross-checked on disk before it counts.
    """

    invocation: subprocess.CompletedProcess[str]
    prefix: Path
    workspace: Path
    home: Path
    checkout_root: Path

    # the identity the PRODUCER returned when it minted this candidate, and
    # what the installed artifact independently says about itself
    minted: CandidateIdentity
    measured_distribution_digest: str
    claimed_distribution_digest: str
    identity_from_the_measured_bytes: str

    # a SECOND real candidate, built from different material and weighed too
    other_candidate: str
    other_measured_distribution_digest: str
    other_claimed_distribution_digest: str
    identity_from_the_other_measured_bytes: str
    reported_candidate: str
    reported_composition: str
    reported_composition_on_second_run: str

    # (a) specialist output correlated to material really installed and read
    specialist_output: str
    role_token: str
    role_token_file_count: int
    skill_token: str
    skill_token_file_count: int
    project_rule_nonce: str
    declared_obligation: str
    obligation_effect_carries_nonce: bool

    # (b) the approval the SELECTED ROLE declares, at the real boundary
    declared_approval: str
    role_files_declaring: int
    machine_grants_of_the_approval: int
    policy_decoy_planted: bool
    granting_authority_is_the_host_policy: bool
    guarded_effect_with_approval: bool
    guarded_effect_without_approval: bool
    refused_approval_exit: int
    refused_approval_remedy: str

    # (c) one NATIVE Codex lifecycle event, and its effect counted in the file
    native_host_binary: Path
    native_decoy_in_the_candidate: Path
    native_decoy_is_executable: bool
    native_decoy_was_invoked: bool
    native_host_version: str
    native_host_exit: int
    native_registration_events: frozenset[str]
    native_tool_the_host_offered: str
    native_event_nonce: str
    native_tool_call_reported_back: bool
    native_reaction_log: Path | None
    native_marks_before: int
    native_reactions: tuple[dict[str, Any], ...]
    native_tool_outcome: str
    native_forbidden_effect_happened: bool
    native_commands_reaching_the_checkout: int
    native_transcript: str

    # (d) one loop, bound to the id its arming returned, counted BY KIND
    loop_id: str
    loop_step_exits: dict[str, int]
    loop_records_before_the_tick: tuple[str, ...]
    loop_records_after_the_tick: tuple[str, ...]
    loop_records_after_the_retick: tuple[str, ...]
    retick_exit: int

    # (e) the Claude surface as the test digested it, either side of the install
    claude_digest_before: str
    claude_digest_after: str

    # (f) provenance and self-sufficiency of the installed candidate
    provenance: InstalledProvenance | None
    provenance_module_is_recorded: bool
    prefix_paths_naming_the_checkout: tuple[str, ...]
    redirecting_path_files: tuple[str, ...]
    real_package_files: int
    decoy_package_planted: bool
    decoy_marker_present: bool

    # (g) private material, by path, against the real install inventory
    unrecorded_installed: tuple[str, ...]
    phantom_recorded: tuple[str, ...]
    installed_inventory: frozenset[str]
    private_paths: frozenset[str]
    public_paths_installed: int

    # -- properties, never designations -------------------------------------

    def ran_from_the_clean_prefix(self) -> tuple[str, ...]:
        """Reported paths that do NOT resolve inside the prefix, if any.

        Empty means every path the clean process attributed its own code to --
        the executable, the module that served the journey, and each import
        root -- is a real file or directory under the installed prefix once
        symlinks are resolved.
        """
        if self.provenance is None:
            return ("no provenance was reported at all",)
        if not self.provenance.import_roots:
            return ("the clean process reported no import roots at all",)
        if not str(self.provenance.module_file):
            return ("the clean process named no module as having served it",)
        if not self.provenance_module_is_recorded:
            return (
                f"{self.provenance.module_file} is not listed in the artifact's "
                "own record of what it installed",
            )
        prefix = self.prefix.resolve()
        strays: list[str] = []
        for path in self.provenance.every_path():
            if not str(path):
                strays.append("an empty path was reported")
                continue
            resolved = path.resolve()
            if not resolved.exists():
                strays.append(f"{resolved} does not exist")
            elif prefix not in resolved.parents and resolved != prefix:
                strays.append(str(resolved))
        return tuple(strays)

    def borrowed_from_the_checkout(self) -> tuple[str, ...]:
        """Every way the installed candidate was found reaching back to source."""
        findings = list(self.prefix_paths_naming_the_checkout)
        findings.extend(self.redirecting_path_files)
        if str(self.checkout_root.resolve()) in self.invocation.stdout:
            findings.append("the checkout root appears in the journey's own output")
        if self.native_commands_reaching_the_checkout:
            findings.append(
                f"{self.native_commands_reaching_the_checkout} registered hook "
                "command(s) point at the checkout"
            )
        return tuple(findings)

    def specialist_quoted(self, token: str) -> bool:
        return bool(token) and token in self.specialist_output

    def leaked_private_paths(self) -> tuple[str, ...]:
        """Installed paths that match a catalogue-private path, component-wise."""
        leaked: list[str] = []
        for installed in sorted(self.installed_inventory):
            parts = installed.split("/")
            for private in self.private_paths:
                private_parts = private.split("/")
                window = len(private_parts)
                if any(
                    parts[index : index + window] == private_parts
                    for index in range(len(parts) - window + 1)
                ):
                    leaked.append(installed)
                    break
        return tuple(leaked)


class InstalledParityJourney:
    """The one service that publishes, installs and drives the whole chain."""

    def __init__(self) -> None:
        self.build_inputs = BuildInputs.for_this_run()
        self._identity: CandidateIdentity | None = None
        self._links: list[ChainLink] = []
        self._approval_can_be_honoured = True
        self._foreign_link: ChainLink | None = None
        self._preserves_foreign_material = True
        self._retick_after_stop = False

    # -- the one identity, minted by production -----------------------------

    @property
    def identity(self) -> CandidateIdentity:
        """The candidate the producer minted for THIS run's build inputs.

        Never a constant: the inputs were invented in ``__init__`` and the
        value comes back from production. An implementation that answers with
        a fixed digest cannot satisfy any scenario in this slice.
        """
        if self._identity is None:
            self._identity = CandidateIdentity(
                candidate=self._mint_identity(),
                composition=f"codex-cli-linux-native-{uuid.uuid4().hex[:12]}",
            )
        return self._identity

    def publish_candidate(self) -> CandidateIdentity:
        return self.identity

    def will_publish_through_the_real_producer(self) -> str:
        """The team's intention, recorded before anything is built.

        The skeleton's candidate is minted inside the journey itself, by the
        real producer, so nothing is fixed here: this step states what the team
        did, and the artifact -- with its identity -- appears when the user
        installs it.
        """
        return "one candidate, to be minted by the real producer"

    def _mint_identity(self) -> str:
        """Ask production for the candidate id of this run's build inputs."""
        from des import CodexParityComposition

        mint = getattr(CodexParityComposition, "mint_candidate_identity", None)
        if mint is None:
            raise AssertionError(
                "__SCAFFOLD__ WHAT: production cannot tell this run which "
                "candidate its build inputs mint, so the only identity a test "
                "could use would be one it wrote down itself. WHY: an identity "
                "the test supplies proves nothing -- every receipt would agree "
                "with the test rather than with the artifact, and a build that "
                "silently changed identity would still pass. HOW: implement "
                "CodexParityComposition.mint_candidate_identity(build_inputs=...) "
                "returning the candidate id minted from those exact inputs."
            )
        minted = str(mint(build_inputs=self.build_inputs.as_public()))
        other = str(mint(build_inputs=self.build_inputs.with_other_bytes()))
        if not minted or minted == FOREIGN_CANDIDATE:
            raise AssertionError(
                f"WHAT: the producer minted {minted!r} for this run's build "
                "inputs. WHY: an empty or placeholder identity cannot bind any "
                "crossing to the artifact the user installed. HOW: mint the "
                "candidate id from the three declared build inputs."
            )
        if minted == other:
            raise AssertionError(
                "WHAT: two DIFFERENT sets of build inputs minted the same "
                f"identity {minted!r}. WHY: one identity read once is an "
                "anecdote -- it is equally consistent with an identity that is "
                "derived from the bytes and with a constant the code returns "
                "whatever it is given. Only a second, different input showing a "
                "different answer tells them apart, and a candidate whose "
                "identity does not move with its bytes cannot detect a "
                "substituted artifact. HOW: derive the identity from the "
                "distribution digest, the public manifest and the build recipe."
            )
        return minted

    # -- the assembled surface (walking skeleton only) ----------------------

    def publish_install_and_walk(self, workspace: Path) -> ObservedJourney:
        """Mint, install clean, then OBSERVE the effects on the clean machine.

        Ordered so the producer is reached before any distribution is built: at
        tip it does not exist, so this fails semantically without a build. Once
        it lands, the identical call performs the real build, the real isolated
        install, and every observation below is taken by this test against the
        workspace, the prefix, a native lifecycle invocation or an exit code.
        """
        home = workspace / "home"
        nonce = self._plant_the_users_machine(workspace)
        claude_before = self._digest_claude_surface(workspace)

        candidate = self._mint_through_the_real_producer()
        minted = self._identity_of(candidate)
        # The bytes are the authority here, not another producer surface: the
        # test weighs the artifact itself, and the published identity has to be
        # the one those bytes mint. Checking the published surface against
        # another producer surface alone would still be the producer vouching
        # for itself.
        artifact = self._artifact_of(candidate)
        measured = self._digest_of(artifact)
        from_the_measured_bytes = self._identity_from_the_measured_bytes(
            measured, self.build_inputs.as_published()
        )

        # And a SECOND candidate, built for real from different material. A
        # mint that answers well to two fabricated inputs can still fail on two
        # genuine builds, and two genuine builds are what the product lives.
        other = self._mint_a_second_published_candidate()
        other_measured = self._digest_of(self._artifact_of(other))
        prefix = self._install_into_a_clean_prefix(candidate, workspace)
        claude_after = self._digest_claude_surface(workspace)

        journey = self._invoke(
            prefix, workspace, "codex-parity-journey", "--report", "json"
        )
        second = self._invoke(
            prefix, workspace, "codex-parity-journey", "--report", "json"
        )
        report = self._json(journey.stdout)

        specialist = self._invoke(
            prefix, workspace, "codex-role", "run", "--role", SELECTED_ROLE
        )
        installed_text = self._installed_corpus(prefix)
        role_token, role_files = self._discriminating_token(installed_text, "role")
        skill_token, skill_files = self._discriminating_token(installed_text, "skill")

        # Only the SELECTED role -- the HOST's role file -- declares what it
        # must do and what it needs.
        role_material = self._host_role_material(home)
        obligation = self._declared_value(role_material, "observable-obligation")
        approval = self._declared_value(role_material, "requires-approval")

        self._invoke(prefix, workspace, "codex-role", "act", "--role", SELECTED_ROLE)
        granted = self._guarded_effect(workspace, role_material)
        self._clear_guarded_effect(workspace, role_material)
        decoy_policy = self._plant_a_policy_decoy(home, approval)
        grants = self._machine_grants_of(home, approval, frozenset(role_material))
        self._withdraw_the_grant(grants, approval)
        refused = self._invoke(
            prefix,
            workspace,
            "codex-role",
            "act",
            "--role",
            SELECTED_ROLE,
            "--report",
            "json",
        )
        withheld = self._guarded_effect(workspace, role_material)

        native = self._let_the_real_host_attempt_a_forbidden_action(
            prefix, workspace, minted
        )

        loop = self._walk_one_loop(prefix, workspace)

        return ObservedJourney(
            invocation=journey,
            prefix=prefix,
            workspace=workspace,
            home=home,
            checkout_root=Path(__file__).resolve().parents[5],
            minted=CandidateIdentity(
                candidate=minted,
                composition=str(report.get("host_composition_id", "")),
            ),
            measured_distribution_digest=measured,
            claimed_distribution_digest=self._claimed_digest(candidate),
            identity_from_the_measured_bytes=from_the_measured_bytes,
            other_candidate=self._identity_of(other),
            other_measured_distribution_digest=other_measured,
            other_claimed_distribution_digest=self._claimed_digest(other),
            identity_from_the_other_measured_bytes=(
                self._identity_from_the_measured_bytes(
                    other_measured, self.build_inputs.as_other_published()
                )
            ),
            reported_candidate=str(report.get("candidate_id", "")),
            reported_composition=str(report.get("host_composition_id", "")),
            reported_composition_on_second_run=str(
                self._json(second.stdout).get("host_composition_id", "")
            ),
            specialist_output=specialist.stdout,
            role_token=role_token,
            role_token_file_count=role_files,
            skill_token=skill_token,
            skill_token_file_count=skill_files,
            project_rule_nonce=nonce,
            declared_obligation=obligation,
            obligation_effect_carries_nonce=self._obligation_fulfilled(
                workspace, obligation, nonce
            ),
            declared_approval=approval,
            role_files_declaring=len(role_material),
            machine_grants_of_the_approval=len(grants),
            policy_decoy_planted=decoy_policy.is_file(),
            granting_authority_is_the_host_policy=(
                self._authority_is_not_the_declaration(home, frozenset(role_material))
            ),
            guarded_effect_with_approval=granted,
            guarded_effect_without_approval=withheld,
            refused_approval_exit=refused.returncode,
            refused_approval_remedy=self._structured_remedy(refused.stdout),
            native_host_binary=native.host_binary,
            native_decoy_in_the_candidate=native.decoy_in_the_candidate,
            native_decoy_is_executable=native.decoy_is_executable,
            native_decoy_was_invoked=native.decoy_was_invoked,
            native_host_version=native.host_version,
            native_registration_events=native.registered_events,
            native_tool_the_host_offered=native.tool_the_host_offered,
            native_host_exit=native.host_exit,
            native_event_nonce=native.event_nonce,
            native_tool_call_reported_back=native.tool_call_reported_back,
            native_reaction_log=native.reaction_log,
            native_marks_before=native.marks_before,
            native_reactions=native.reactions,
            native_tool_outcome=native.tool_outcome_text,
            native_forbidden_effect_happened=native.forbidden_effect_happened,
            native_commands_reaching_the_checkout=native.commands_reaching_the_checkout,
            native_transcript=native.transcript,
            loop_id=loop["loop_id"],
            loop_step_exits=loop["exits"],
            loop_records_before_the_tick=loop["before"],
            loop_records_after_the_tick=loop["after_tick"],
            loop_records_after_the_retick=loop["after_retick"],
            retick_exit=loop["retick_exit"],
            claude_digest_before=claude_before,
            claude_digest_after=claude_after,
            provenance=InstalledProvenance.read(report),
            provenance_module_is_recorded=self._module_is_recorded(report, prefix),
            prefix_paths_naming_the_checkout=self._paths_naming_the_checkout(prefix),
            redirecting_path_files=self._redirecting_path_files(prefix),
            real_package_files=self._real_package_files(prefix),
            decoy_package_planted=self._decoy_package_is_still_there(workspace),
            decoy_marker_present=bool(list(home.rglob(f"*{DECOY_MARKER}*"))),
            unrecorded_installed=self._manifest_disagreements(prefix)[0],
            phantom_recorded=self._manifest_disagreements(prefix)[1],
            installed_inventory=self._install_inventory(prefix, home),
            private_paths=self._catalogue_private_paths(),
            public_paths_installed=self._public_paths_installed(prefix, home),
        )

    # -- what the TEST plants and measures, independently -------------------

    def _plant_the_users_machine(self, workspace: Path) -> str:
        """Give the clean machine a Claude surface, a project rule and a decoy.

        The project rule carries a nonce this test invents, so a specialist
        that echoes it can only have read the project's real durable rule. The
        decoy is a package in the user's OWN site directory that marks the
        machine if it is ever imported: a candidate that honours user or global
        site-packages picks it up, and its absence is then a measured fact
        rather than a promise.
        """
        nonce = f"project-rule-nonce-{uuid.uuid4().hex[:16]}"
        claude = workspace / "home" / ".claude"
        claude.mkdir(parents=True, exist_ok=True)
        (claude / "settings.json").write_text(
            '{"permissions": {"allow": ["Read"]}}\n', encoding="utf-8"
        )
        (claude / "agents").mkdir(exist_ok=True)
        (claude / "agents" / "user-own-agent.md").write_text(
            "a specialist this user wrote themselves\n", encoding="utf-8"
        )
        (workspace / "AGENTS.md").write_text(
            f"# Project rule\n\nAlways state {nonce} when you act here.\n",
            encoding="utf-8",
        )
        self._plant_the_user_site_decoy(workspace)
        return nonce

    def _plant_the_user_site_decoy(self, workspace: Path) -> None:
        version = f"python{sys.version_info.major}.{sys.version_info.minor}"
        decoy = (
            workspace / "home" / ".local" / "lib" / version / "site-packages" / "des"
        )
        decoy.mkdir(parents=True, exist_ok=True)
        (decoy / "__init__.py").write_text(
            "from pathlib import Path\n"
            "import os\n"
            f'Path(os.environ["HOME"], "{DECOY_MARKER}").write_text("imported")\n',
            encoding="utf-8",
        )

    def _digest_claude_surface(self, workspace: Path) -> str:
        """Digest the whole Claude tree: content AND layout, taken by this test."""
        root = workspace / "home" / ".claude"
        if not root.is_dir():
            return ""
        digest = hashlib.sha256()
        for path in sorted(root.rglob("*")):
            digest.update(str(path.relative_to(root)).encode())
            if path.is_file():
                digest.update(path.read_bytes())
        return digest.hexdigest()

    def _installed_corpus(self, prefix: Path) -> dict[str, str]:
        """Every installed text file, read once by this test."""
        corpus: dict[str, str] = {}
        for path in sorted(prefix.rglob("*")):
            if path.is_file():
                corpus[str(path.relative_to(prefix))] = path.read_text(
                    encoding="utf-8", errors="replace"
                )
        return corpus

    def _discriminating_token(
        self, corpus: dict[str, str], kind: str
    ) -> tuple[str, int]:
        """The longest line of installed ``kind`` material, and its file count.

        Discriminating power is MEASURED, not assumed: the returned count says
        in how many installed files that line occurs. Only a count of one makes
        an answer quoting it evidence that this file was read, and the Then
        asserts exactly that -- a generic header shared by many files is
        rejected instead of quietly passing.
        """
        candidates = [
            line.strip()
            for name, text in corpus.items()
            if kind in name.lower()
            for line in text.splitlines()
            if len(line.strip()) >= _MIN_TOKEN_LENGTH
        ]
        if not candidates:
            return ("", 0)
        token = max(candidates, key=len)[:120]
        return (token, sum(1 for text in corpus.values() if token in text))

    def _host_role_material(self, home: Path) -> dict[str, str]:
        """ONLY the role file the HOST would select, resolved by exact identity.

        The role a Codex user runs lives in the host's own agents directory, so
        a file in the prefix whose NAME happens to contain the role's is not
        that role: it could declare an obligation and an approval the host
        never sees, and the selected role would be judged against a stranger's
        bar. Identity is matched exactly -- the role's declared name, else its
        file stem -- and zero or several matches leave the material empty so
        the scenario says so rather than picking one.
        """
        agents = home / ".codex" / "agents"
        if not agents.is_dir():
            return {}
        matching = {
            str(path): path.read_text(encoding="utf-8", errors="replace")
            for path in sorted(agents.glob("*.toml"))
            if self._role_identity(path) == SELECTED_ROLE
        }
        return matching if len(matching) == 1 else {}

    def _role_identity(self, path: Path) -> str:
        """The identity a host role file declares for itself."""
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = line.strip()
            if stripped.lower().startswith("name ="):
                declared = stripped.split("=", 1)[1].strip().strip('"').strip("'")
                return declared.removeprefix("nw-")
        return path.stem.removeprefix("nw-")

    def _declared_value(self, corpus: dict[str, str], key: str) -> str:
        """A value the SELECTED ROLE declares for itself.

        Read from the artifact on disk in either native form (``key = "v"`` in
        role TOML, ``key: v`` in a skill or instruction file). The test never
        invents it: what the specialist must do, and which approval it needs,
        are facts of the installed role.
        """
        needles = (f"{key} =", f"{key}:")
        for _, text in sorted(corpus.items()):
            for line in text.splitlines():
                stripped = line.strip()
                for needle in needles:
                    if stripped.lower().startswith(needle):
                        return stripped[len(needle) :].strip().strip('"').strip("'")
        return ""

    def _structured_remedy(self, reported: str) -> str:
        """The refusal's WHAT/WHY/HOW, read as STRUCTURE not as prose.

        A refusal the user can act on has three named parts. Reading them out
        of a structured diagnostic -- rather than searching free text -- is
        what stops a bare message, or a stack trace, from counting as guidance.
        """
        diagnostic = self._json(reported).get("diagnostic")
        if not isinstance(diagnostic, dict):
            return ""
        parts = [
            str(diagnostic.get(part, "")).strip() for part in ("what", "why", "how")
        ]
        return " ".join(parts) if all(parts) else ""

    def _module_is_recorded(self, report: dict[str, Any], prefix: Path) -> bool:
        """Is the module that served the journey in the artifact's OWN record?

        The clean process names its own module; the record is what the build
        says it shipped. Requiring both to agree makes the provenance a
        two-source fact instead of a self-declaration.
        """
        provenance = InstalledProvenance.read(report)
        if provenance is None or not str(provenance.module_file):
            return False
        try:
            module = str(provenance.module_file.resolve().relative_to(prefix.resolve()))
        except ValueError:
            return False
        return Path(module).as_posix() in self._recorded_paths(prefix)

    def _decoy_package_is_still_there(self, workspace: Path) -> bool:
        """Was the decoy really on the machine while the candidate ran?

        An absent marker means nothing if the decoy was never planted: the
        scenario would be asserting that a package which does not exist was
        not imported.
        """
        version = f"python{sys.version_info.major}.{sys.version_info.minor}"
        decoy = (
            workspace
            / "home"
            / ".local"
            / "lib"
            / version
            / "site-packages"
            / "des"
            / "__init__.py"
        )
        return decoy.is_file()

    def _obligation_fulfilled(self, workspace: Path, declared: str, nonce: str) -> bool:
        """Did the specialist do what its installed role declared it must do?"""
        if not declared:
            return False
        effect = workspace / declared
        return effect.is_file() and nonce in effect.read_text(
            encoding="utf-8", errors="replace"
        )

    def _guarded_effect(self, workspace: Path, corpus: dict[str, str]) -> bool:
        """Did the approval-guarded action leave the effect the role declares?"""
        declared = self._declared_value(corpus, "guarded-effect")
        return bool(declared) and (workspace / declared).is_file()

    def _clear_guarded_effect(self, workspace: Path, corpus: dict[str, str]) -> None:
        """Remove the guarded mark, so the second leg is measured on its own.

        Without this the approved leg's effect would still be on disk when the
        unapprovable leg is judged, and an action that ran anyway would be
        credited to the earlier, legitimate run.
        """
        declared = self._declared_value(corpus, "guarded-effect")
        if declared:
            (workspace / declared).unlink(missing_ok=True)

    def _host_policy_documents(self, home: Path) -> tuple[Path, ...]:
        """The policy the HOST actually RESOLVES for this invocation.

        Authority is not "somewhere on the machine", and it is not "a file of
        the right shape" either: it is the document the host really consults
        when it decides what may happen. This journey selects no profile, so
        that is exactly the base configuration -- a sibling with a
        profile-looking name is never resolved, and what the host never reads
        cannot concede anything.
        """
        base = home / ".codex" / "config.toml"
        # A profile layer counts only when the host was actually ASKED for one;
        # this journey selects none, so the base configuration is the whole of
        # the resolved policy. A sibling with a profile-shaped name is never
        # resolved, and what the host never reads cannot concede anything.
        return (base,) if base.is_file() else ()

    def _plant_a_policy_decoy(self, home: Path, approval: str) -> Path:
        """A file shaped like host policy, granting the approval, never read.

        The host resolves a profile only when asked for one, and this journey
        asks for none -- so this document is authority in appearance and in
        nothing else. Planting it is what turns "a decoy would not be read"
        from a claim about the code into an observation: if it were ever
        consulted, the withdrawal from the real policy would leave the guarded
        action permitted and the scenario would say so.
        """
        decoy = home / ".codex" / "decoy.config.toml"
        if approval:
            decoy.parent.mkdir(parents=True, exist_ok=True)
            decoy.write_text(f'granted_approvals = ["{approval}"]\n', encoding="utf-8")
        return decoy

    def _machine_grants_of(
        self, home: Path, approval: str, role_files: frozenset[str]
    ) -> tuple[tuple[Path, str], ...]:
        """Where THIS MACHINE actually grants the approval, on its OWN authority.

        Two things have to hold together, and only one of them is about the
        subject. The grant must be a policy FIELD whose VALUE carries the
        approval -- a file that merely contains the word is not a grant. And it
        must sit in a document the HOST treats as policy: the role's own
        statement of what it REQUIRES is a perfectly identified subject, a
        precise file and a precise field, and it still has no title to grant
        anything. A requirement that satisfies itself is not an authority.
        """
        grants: list[tuple[Path, str]] = []
        if not approval:
            return ()
        for path in self._host_policy_documents(home):
            if str(path) in role_files:
                continue
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                match = _GRANT_FIELD.match(line.strip())
                if match and approval in match.group("value"):
                    grants.append((path, match.group("field")))
        return tuple(grants)

    def _authority_is_not_the_declaration(
        self, home: Path, role_files: frozenset[str]
    ) -> bool:
        """Is the granting authority a different file from the role's claim?"""
        policy = {str(path) for path in self._host_policy_documents(home)}
        return bool(policy) and not (policy & set(role_files))

    def _withdraw_the_grant(
        self, grants: tuple[tuple[Path, str], ...], approval: str
    ) -> None:
        """Take the approval out of the authority's field, and nothing else.

        Deleting every line that mentions the approval would also delete the
        role's requirement, and the second leg would then be refused for the
        wrong reason -- a role that no longer asks for anything is not a
        machine that cannot grant it.
        """
        for path, granting_field in grants:
            rewritten: list[str] = []
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                match = _GRANT_FIELD.match(line.strip())
                if (
                    match
                    and match.group("field") == granting_field
                    and approval in match.group("value")
                ):
                    withdrawn = self._value_without(match.group("value"), approval)
                    rewritten.append(f"{granting_field} = {withdrawn}")
                else:
                    rewritten.append(line)
            path.write_text("\n".join(rewritten) + "\n", encoding="utf-8")

    @staticmethod
    def _value_without(value: str, approval: str) -> str:
        """The same policy value with this one approval removed."""
        stripped = value
        for form in (f'"{approval}"', f"'{approval}'", approval):
            stripped = stripped.replace(form, "")
        cleaned = stripped.replace(",,", ",").replace("[,", "[").replace(",]", "]")
        cleaned = cleaned.replace("[ ,", "[").replace(", ]", "]").strip()
        return cleaned if cleaned not in {"", "[]", "true"} else "false"

    def _let_the_real_host_attempt_a_forbidden_action(
        self, prefix: Path, workspace: Path, candidate: str
    ) -> NativeHostObservation:
        """Boot the REAL host and let IT attempt one forbidden action.

        Declaring the hook in the native format proves configuration; only the
        host calling it proves activation, and only the forbidden action
        failing to happen proves enforcement. So the test does not fire the
        hook itself: it boots the real binary against the installed candidate,
        with a deterministic mock provider standing in for the model, and then
        measures what is on the machine.
        """
        return NativeCodexHost(
            home=workspace / "home", workspace=workspace, prefix=prefix
        ).observe_one_forbidden_action(self._checkout_root(), candidate)

    def _walk_one_loop(self, prefix: Path, workspace: Path) -> dict[str, Any]:
        """Arm one loop, then bind every later step to the id arming returned."""
        home = workspace / "home"
        armed = self._invoke(
            prefix,
            workspace,
            "loop",
            "arm",
            "--project",
            str(workspace),
            "--report",
            "json",
        )
        loop_id = str(self._json(armed.stdout).get("loop_id", ""))
        before = self._typed_loop_records(home, loop_id)
        tick = self._invoke(prefix, workspace, "loop", "tick", "--loop", loop_id)
        after_tick = self._typed_loop_records(home, loop_id)
        stop = self._invoke(prefix, workspace, "loop", "stop", "--loop", loop_id)
        retick = self._invoke(prefix, workspace, "loop", "tick", "--loop", loop_id)
        return {
            "loop_id": loop_id,
            "exits": {
                "arm": armed.returncode,
                "tick": tick.returncode,
                "stop": stop.returncode,
            },
            "before": before,
            "after_tick": after_tick,
            "after_retick": self._typed_loop_records(home, loop_id),
            "retick_exit": retick.returncode,
        }

    def _typed_loop_records(self, home: Path, loop_id: str) -> tuple[str, ...]:
        """Durable records for THIS loop, canonically, as an ordered set.

        Two disciplines in one measurement. First, a file that merely mentions
        the loop is not a record: arming writes one too, so only a TYPED entry
        -- one that says what kind of occurrence it is, which loop it belongs
        to and which occurrence it is -- is counted. Second, the records are
        returned canonically rather than counted, because a count cannot tell
        conservation from replacement: a stop that rewrites, substitutes or
        corrupts the attestation while keeping one tick and one attestation
        would read as untouched.
        """
        records: list[str] = []
        if not loop_id or not home.is_dir():
            return ()
        for path in sorted(home.rglob("*")):
            if not path.is_file():
                continue
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                stripped = line.strip()
                if not stripped.startswith("{") or loop_id not in stripped:
                    continue
                record = self._json(stripped)
                if not self._is_a_loop_record(record, loop_id):
                    continue
                records.append(
                    json.dumps(record, sort_keys=True, separators=(",", ":"))
                )
        return tuple(sorted(records))

    @classmethod
    def _is_a_loop_record(cls, record: dict[str, Any], loop_id: str) -> bool:
        """An attested occurrence of this loop, not merely a shaped object.

        Fields being present is what a fabricated pair of minimal objects also
        satisfies: two lines of JSON with the right keys would survive the stop
        and read as conserved attested work. So a record counts only when it
        declares the schema it was written against, carries the work it
        attests, and BINDS that work with a digest this test recomputes -- an
        integrity check whose answer the record cannot simply assert.
        """
        payload = record.get("payload")
        if (
            str(record.get("loop_id", "")) != loop_id
            or not str(record.get("kind", ""))
            or not str(record.get("record_id", ""))
            or not str(record.get("schema_version", ""))
            or not isinstance(payload, dict)
            or not payload
        ):
            return False
        return str(record.get("payload_digest", "")) == cls._payload_digest(payload)

    @staticmethod
    def _payload_digest(payload: dict[str, Any]) -> str:
        """The digest the record's own payload must answer to."""
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()

    @staticmethod
    def attests_the_tick(records: tuple[str, ...]) -> bool:
        """Does an attestation stand for the tick that actually ran?

        The binding, not the shape: an attestation names the record identity of
        the occurrence it attests, so a pair of objects fabricated side by side
        -- each well formed, neither referring to the other -- is refused.
        """
        parsed = [json.loads(raw) for raw in records]
        ticks = {
            str(record.get("record_id", ""))
            for record in parsed
            if str(record.get("kind", "")).lower() == "tick"
        }
        return any(
            str(record.get("attests", "")) in ticks and ticks
            for record in parsed
            if str(record.get("kind", "")).lower() == "attestation"
        )

    @staticmethod
    def kinds_in(records: tuple[str, ...]) -> dict[str, int]:
        """How many records of each kind, for the scenario to read."""
        counts: dict[str, int] = {}
        for raw in records:
            kind = str(json.loads(raw).get("kind", "")).lower()
            counts[kind] = counts.get(kind, 0) + 1
        return counts

    # -- provenance and self-sufficiency, measured on the prefix ------------

    def _checkout_root(self) -> Path:
        return Path(__file__).resolve().parents[5]

    def _paths_naming_the_checkout(self, prefix: Path) -> tuple[str, ...]:
        """Installed files whose CONTENT points back at the developer's tree.

        Catches editable installs, ``.pth`` redirection, ``direct_url.json``
        and recorded source paths -- every way an install can look complete
        while actually being served by the checkout.
        """
        needle = str(self._checkout_root())
        return tuple(
            str(path.relative_to(prefix))
            for path in sorted(prefix.rglob("*"))
            if path.is_file()
            and path.suffix in {".pth", ".py", ".json", ".txt", ""}
            and needle in path.read_text(encoding="utf-8", errors="replace")
        )

    def _redirecting_path_files(self, prefix: Path) -> tuple[str, ...]:
        """``.pth`` lines that can serve the candidate from somewhere else.

        Two ways a path file escapes, both counted here:

        * an EXECUTABLE line (``import ...``) runs arbitrary code at interpreter
          start and can install any finder it likes. It cannot be read as a
          destination, so it is refused rather than skipped -- skipping it is
          how the most capable redirection would pass unseen;
        * a RELATIVE entry, which the interpreter resolves against the
          directory the path file lives in -- never against whatever the
          working directory happened to be.
        """
        resolved = prefix.resolve()
        straying: list[str] = []
        for path in sorted(prefix.rglob("*.pth")):
            site = path.parent
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                entry = line.strip()
                if not entry or entry.startswith("#"):
                    continue
                if entry.startswith(("import ", "import\t")):
                    straying.append(
                        f"{path.relative_to(prefix)} runs code at startup: {entry}"
                    )
                    continue
                target = (site / entry).resolve()
                if resolved not in target.parents and target != resolved:
                    straying.append(f"{path.relative_to(prefix)} -> {target}")
        return tuple(straying)

    def _real_package_files(self, prefix: Path) -> int:
        """Non-empty ``des`` package files that really live under the prefix."""
        return sum(
            1
            for path in prefix.rglob("des/*.py")
            if path.is_file() and not path.is_symlink() and path.stat().st_size > 0
        )

    # -- the install inventory and what the catalogue keeps private ---------

    def _vendor_destinations(self, prefix: Path, home: Path) -> tuple[Path, ...]:
        """Every place this candidate really deposits material.

        The prefix is not the whole story: a Codex install also writes roles
        into the host's own agents directory and skills into the user's agent
        home, so an exclusion checked against the prefix alone would declare
        clean a machine carrying private material two directories away.
        """
        return (prefix, home / ".codex", home / ".agents")

    def _install_inventory(self, prefix: Path, home: Path) -> frozenset[str]:
        """Everything the candidate really put on the machine.

        The union of every vendor destination's tree (files AND directories)
        and the paths the artifact's own ``RECORD`` claims -- so material
        recorded by the wheel is counted even if the tree hides it.
        """
        tree: set[str] = set()
        for root in self._vendor_destinations(prefix, home):
            if root.is_dir():
                tree.update(str(path.relative_to(root)) for path in root.rglob("*"))
        recorded = {
            line.split(",")[0].strip()
            for record in prefix.rglob("*.dist-info/RECORD")
            for line in record.read_text(
                encoding="utf-8", errors="replace"
            ).splitlines()
            if line.strip()
        }
        return frozenset(tree | recorded)

    def _record_entries(self, record: Path) -> tuple[str, ...]:
        """The paths one manifest claims, parsed as the CSV it actually is.

        Splitting on the first comma loses a quoted filename that contains one:
        the entry is truncated and then read as a path nobody installed. A real
        reader is the only way the manifest is compared as what it is.
        """
        rows = csv.reader(
            record.read_text(encoding="utf-8", errors="replace").splitlines()
        )
        return tuple(row[0].strip() for row in rows if row and row[0].strip())

    def _recorded_paths(self, prefix: Path) -> frozenset[str]:
        """Every path the artifact's manifests claim, in ONE universe.

        Entries are written relative to the site directory that holds the
        manifest, and they may climb out of it: ``../../../bin/des`` is an
        ordinary, valid entry for an installed console script. Resolving each
        entry against its own site directory -- which is also what collapses
        ``.`` and ``..``, something re-expressing the text never does -- and
        then relating it to the PREFIX puts manifest and tree in the same
        universe. Compared inside its own site directory instead, that script
        reads as a phantom while the file sits in the prefix.
        """
        root = prefix.resolve()
        claimed: set[str] = set()
        for record in prefix.rglob("*.dist-info/RECORD"):
            site = record.parent.parent
            for entry in self._record_entries(record):
                resolved = (site / entry).resolve()
                try:
                    claimed.add(resolved.relative_to(root).as_posix())
                except ValueError:
                    claimed.add(f"outside the install: {resolved}")
        return frozenset(claimed)

    def _installed_paths(self, prefix: Path) -> frozenset[str]:
        """Every file the install really produced, in that same universe."""
        root = prefix.resolve()
        return frozenset(
            path.resolve().relative_to(root).as_posix()
            for path in prefix.rglob("*")
            if path.is_file()
        )

    def _manifest_disagreements(self, prefix: Path) -> tuple[tuple[str, ...], ...]:
        """Where the artifact's manifest and the installed tree disagree.

        Both directions, over the WHOLE install rather than site directory by
        site directory, because each hides a different substitution: a file
        installed but not recorded is material that arrived without the
        manifest accounting for it -- and one placed outside every site
        directory would otherwise never be looked at at all -- while a recorded
        entry with nothing behind it is a manifest describing an install that
        did not happen.
        """
        installed = self._installed_paths(prefix)
        claimed = self._recorded_paths(prefix)
        return (tuple(sorted(installed - claimed)), tuple(sorted(claimed - installed)))

    def _catalogue_private_paths(self) -> frozenset[str]:
        """Paths the framework catalogue says a public candidate must not carry.

        An independent oracle: the catalogue is read structurally by this test
        (name plus its own ``public`` flag), and each private name is mapped to
        the PATHS it would occupy -- its agent document and its skill package
        directory -- so a directory, a nested resource or a differently-named
        file cannot slip through a name-only comparison.
        """
        catalog = Path("nWave/framework-catalog.yaml")
        if not catalog.is_file():
            return frozenset()
        private: list[str] = []
        current = ""
        for raw in catalog.read_text(encoding="utf-8").splitlines():
            stripped = raw.strip()
            if stripped.endswith(":") and not stripped.startswith("-"):
                current = stripped[:-1]
            elif stripped == "public: false" and current:
                private.append(current)
        ownership = self._skill_ownership()
        private_names = set(private)
        paths: set[str] = set()
        for skill, owners in ownership.items():
            # the distribution's own rule: a skill survives only if some PUBLIC
            # agent owns it, so a skill owned solely by private agents is
            # private material even though the catalogue never names it
            if owners and owners <= private_names:
                paths.add(f"skills/{skill}")
                paths.add(f"skills/{skill}/SKILL.md")
        for name in private:
            # both native shapes: the document form and the host's role form
            paths.add(f"agents/nw-{name}.md")
            paths.add(f"agents/nw-{name}.toml")
            paths.add(f"agents/{name}.toml")
            paths.add(f"skills/nw-{name}")
            paths.add(f"skills/nw-{name}/SKILL.md")
        paths.update({"docs/analysis", "docs/internal", "checklists"})
        return frozenset(paths)

    def _skill_ownership(self) -> dict[str, set[str]]:
        """Which agents own which skill, read from the agents themselves.

        The catalogue names agents, not skills; the real filter keeps a skill
        only when a PUBLIC agent owns it. Deriving that from the agent
        frontmatter -- an independent source inventory, not the producer's
        output -- is what makes a skill owned solely by a private agent count
        as private material.
        """
        ownership: dict[str, set[str]] = {}
        agents = Path("nWave/agents")
        if not agents.is_dir():
            return ownership
        for document in sorted(agents.glob("nw-*.md")):
            owner = document.stem.removeprefix("nw-")
            inside = False
            for raw in document.read_text(encoding="utf-8").splitlines():
                stripped = raw.strip()
                if stripped.startswith("skills:"):
                    inside = True
                    continue
                if inside:
                    if stripped.startswith("- "):
                        ownership.setdefault(stripped[2:].strip(), set()).add(owner)
                        continue
                    break
        return ownership

    def _public_paths_installed(self, prefix: Path, home: Path) -> int:
        """How many PUBLIC specialists the candidate installed, anywhere.

        Absence of private material is only meaningful beside presence of
        public material: an install that ships nothing satisfies every
        exclusion trivially, and this count is what refuses that. Counted
        across the same destinations the exclusion is measured on, in both
        native shapes.
        """
        private = self._catalogue_private_paths()
        found = 0
        for root in self._vendor_destinations(prefix, home):
            if not root.is_dir():
                continue
            for path in root.rglob("*"):
                if not path.is_file() or path.suffix not in {".md", ".toml"}:
                    continue
                relative = str(path.relative_to(root))
                if "agents/" not in f"/{relative}" and not relative.startswith(
                    "agents"
                ):
                    continue
                if not any(entry in relative for entry in private):
                    found += 1
        return found

    # -- production surfaces the skeleton depends on ------------------------

    def _mint_through_the_real_producer(self) -> object:
        """Ask production to build and mint the one published candidate."""
        from des import CodexParityComposition

        producer = getattr(CodexParityComposition, "mint_published_candidate", None)
        if producer is None:
            raise AssertionError(
                "__SCAFFOLD__ WHAT: nothing in production mints a publishable "
                "candidate, so there is no artifact for a user to install. "
                "WHY: without a real producer this journey could only ever "
                "exercise the source checkout, which proves the developer's "
                "tree works and says nothing about what a user receives. "
                "HOW: implement CodexParityComposition.mint_published_candidate "
                "so it builds the distribution and returns its CandidateId."
            )
        return producer(
            requested_platform="CODEX",
            build_inputs=self.build_inputs.as_published(),
        )

    def _artifact_of(self, candidate: object) -> Path:
        """The file the producer actually built, so the test can weigh it."""
        try:
            return Path(str(public_field(candidate, "artifact")))
        except (KeyError, AttributeError):
            raise AssertionError(
                "WHAT: the published candidate does not say which file it is. "
                "WHY: without the artifact itself the only account of the "
                "candidate's bytes would be the producer's own, and a producer "
                "vouching for the bytes it claims to have built attests its own "
                "capability. HOW: return the locator of the distribution that "
                "was built."
            ) from None

    def _digest_of(self, artifact: Path) -> str:
        """The bytes, weighed by the TEST. This is the authority for identity.

        Not the producer's account of its own output: the file on disk. An
        identity that does not follow this digest is an identity nothing on the
        machine can hold to account.
        """
        if not artifact.is_file():
            raise AssertionError(
                f"WHAT: the published candidate names {artifact}, which is not a "
                "file. WHY: an artifact nobody can weigh cannot answer for its "
                "own identity, and every downstream claim would rest on the "
                "producer agreeing with itself. HOW: build a real distribution "
                "and return where it is."
            )
        digest = hashlib.sha256()
        digest.update(artifact.read_bytes())
        return digest.hexdigest()

    def _identity_from_the_measured_bytes(
        self, measured: str, declared: dict[str, str]
    ) -> str:
        """What the identity surface mints for the bytes the TEST weighed.

        The declared inputs are the ones THIS candidate was published from, and
        they travel with it. Re-minting a second candidate under the first
        one's manifest and recipe would ask production for the identity of a
        build nobody made: whatever came back could then agree with neither
        artifact, so the check would fail on its own arithmetic rather than on
        the property, and no correct producer could ever satisfy it.
        """
        from des import CodexParityComposition

        mint = getattr(CodexParityComposition, "mint_candidate_identity", None)
        if mint is None:
            raise AssertionError(
                "__SCAFFOLD__ WHAT: production cannot mint an identity from "
                "declared build inputs. WHY: without it the published identity "
                "could only be checked against the producer's own word. HOW: "
                "implement CodexParityComposition.mint_candidate_identity."
            )
        return str(mint(build_inputs={**declared, "distribution_digest": measured}))

    def _identity_of(self, candidate: object) -> str:
        """The candidate id the producer RETURNED, never one this test chose.

        The build's own inputs are facts of the build -- the exact distribution
        bytes and its public manifest -- so the identity can only come back
        from the producer that assembled them.
        """
        try:
            minted = str(public_field(candidate, "candidate_id"))
        except (KeyError, AttributeError):
            minted = ""
        if not minted or minted == FOREIGN_CANDIDATE:
            raise AssertionError(
                f"WHAT: minting the published candidate returned {minted!r} as "
                "its identity. WHY: without an identity from the producer, "
                "every downstream receipt could only be checked against a value "
                "the test wrote down, and a build that silently changed "
                "identity would still pass. HOW: return the minted CandidateId "
                "from mint_published_candidate."
            )
        return minted

    def _claimed_digest(self, candidate: object) -> str:
        """What the producer SAYS its distribution bytes digest to."""
        try:
            return str(public_field(candidate, "distribution_digest"))
        except (KeyError, AttributeError):
            return ""

    def _mint_a_second_published_candidate(self) -> object:
        """Publish a second candidate for real, from different material.

        Not installed -- only built and weighed. One real build proves the
        producer can name an identity; two real builds of DIFFERENT material
        are what shows the identity follows the artifact rather than the
        occasion, and that is the case a user meets when a rebuild changes
        something.
        """
        from des import CodexParityComposition

        producer = getattr(CodexParityComposition, "mint_published_candidate", None)
        if producer is None:
            raise AssertionError(
                "__SCAFFOLD__ WHAT: nothing in production mints a publishable "
                "candidate, so a second one cannot be built either. WHY: "
                "without two real artifacts nothing shows the identity follows "
                "the bytes. HOW: implement "
                "CodexParityComposition.mint_published_candidate."
            )
        return producer(
            requested_platform="CODEX",
            build_inputs=self.build_inputs.as_other_published(),
        )

    def _install_into_a_clean_prefix(self, candidate: object, workspace: Path) -> Path:
        """Install the minted candidate into a prefix that borrows nothing."""
        from des import CodexParityComposition

        installer = getattr(CodexParityComposition, "install_candidate", None)
        if installer is None:
            raise AssertionError(
                "__SCAFFOLD__ WHAT: production cannot install a minted candidate "
                "into a clean prefix. WHY: an install that is not isolated can "
                "satisfy itself from the source tree, the developer's HOME or a "
                "global install, and every downstream capability claim would "
                "then rest on borrowed bytes. HOW: implement "
                "CodexParityComposition.install_candidate(candidate, prefix, home)."
            )
        return Path(
            installer(candidate, prefix=workspace / "prefix", home=workspace / "home")
        )

    @staticmethod
    def _environment(prefix: Path, home: Path) -> dict[str, str]:
        """A scrubbed environment: no PYTHONPATH, prefix-rooted PATH, own HOME."""
        return {
            "PATH": f"{prefix / 'bin'}{os.pathsep}/usr/bin{os.pathsep}/bin",
            "HOME": str(home),
            "CODEX_HOME": str(home / ".codex"),
        }

    def _invoke(
        self, prefix: Path, workspace: Path, *argv: str
    ) -> subprocess.CompletedProcess[str]:
        """Execute the INSTALLED console script, never the checkout.

        The environment is scrubbed rather than inherited, and cwd is the
        workspace, so the source tree is not even the working directory.
        """
        return subprocess.run(
            [str(prefix / "bin" / "des"), *argv],
            capture_output=True,
            text=True,
            timeout=600,
            cwd=workspace,
            env=self._environment(prefix, workspace / "home"),
        )

    @staticmethod
    def _json(text: str) -> dict[str, Any]:
        try:
            payload = json.loads(text or "{}")
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}

    # -- arranging the chain -----------------------------------------------

    def exercise(self, *links: ChainLink) -> None:
        self._links.extend(links)

    def declared_items(self) -> tuple[str, ...]:
        """Exactly the crossings this scenario asked for, with multiplicity."""
        return tuple(sorted(link.value for link in self._links))

    def approval_cannot_be_honoured(self) -> None:
        """This machine cannot honour the approval the specialist's role requires."""
        self._approval_can_be_honoured = False

    def borrowed_from_another_machine(self, link: ChainLink) -> None:
        """Offer this crossing work done for a different candidate and machine."""
        self._foreign_link = link

    def ticks_again_after_stopping(self) -> None:
        """Attempt one more tick once the loop has been stopped."""
        self._retick_after_stop = True

    # -- driving ------------------------------------------------------------

    def run(self) -> PublishedJourneyRun:
        """Drive the sole production driving port once with the arranged chain."""
        ports = FivePortWitnesses()
        try:
            result = CodexParityJourneyComposition().run(
                self._request(), external_ports=ports.external_ports()
            )
        except (AttributeError, TypeError) as absent:
            raise AssertionError(
                "__SCAFFOLD__ WHAT: the installed candidate cannot answer the "
                "user's journey at all -- its driving surface does not yet "
                f"accept the request ({absent}). WHY: until it does, none of "
                "this user's specialist, safeguard or continued-work "
                "capabilities can be observed, let alone credited to the "
                "candidate they installed. HOW: implement "
                "CodexParityJourneyPort.run so it sequences the arranged "
                "request and returns one structured receipt per crossing."
            ) from None
        return PublishedJourneyRun(result=result, ports=ports, identity=self.identity)

    # -- request assembly (the only place a request is built) ---------------

    def _request(self) -> dict[str, object]:
        return {
            "subject": self._subject(self.identity),
            "build_inputs": self.build_inputs.as_public(),
            "assembled_candidate": {
                "locator": "candidate-1.whl",
                "origin": "ASSEMBLED_DISTRIBUTION",
                "declared_digest": self.build_inputs.distribution_digest,
            },
            "treatment_plan": {
                "subject": self._subject(self.identity),
                "intents": [{"key": "nwave/role.toml"}],
                "preserves_foreign_material": self._preserves_foreign_material,
            },
            "probe": {
                "subject": self._subject(self.identity),
                "workload_digest": "workload-1",
                "witnesses": [self._witness(link) for link in self._links],
                "arms": self._arms(),
            },
            "expected_evidence": {
                "kind": "PROVED",
                "declared_items": [link.value for link in self._links],
                "retick_after_stop": self._retick_after_stop,
            },
        }

    def _witness(self, link: ChainLink) -> dict[str, object]:
        identity = (
            CandidateIdentity(FOREIGN_CANDIDATE, FOREIGN_COMPOSITION)
            if link is self._foreign_link
            else self.identity
        )
        witness: dict[str, object] = {
            "id": link.name.lower().replace("_", "-"),
            "item": link.value,
            "suite": "installed-parity-suite",
            "timeout": 30,
            "candidate_id": identity.candidate,
            "composition_id": identity.composition,
        }
        if link is ChainLink.APPROVAL_IS_ENFORCED_OR_REFUSED:
            witness["approval_can_be_honoured"] = self._approval_can_be_honoured
        return witness

    def _arms(self) -> list[dict[str, object]]:
        return [
            {
                "kind": "CONTROL",
                "nonce": "control-1",
                "clean_absence": True,
                "binary_digest": "binary-1",
                "workload_digest": "workload-1",
            },
            {
                "kind": "TREATMENT",
                "nonce": "treatment-1",
                "candidate_id": self.identity.candidate,
                "isolated_install": True,
                "binary_digest": "binary-1",
                "workload_digest": "workload-1",
            },
        ]

    def _subject(self, identity: CandidateIdentity) -> dict[str, object]:
        return {
            "composition_id": identity.composition,
            "candidate_id": identity.candidate,
            "manifest_digest": self.build_inputs.public_manifest_digest,
            "requested_platform": "CODEX",
            "target_selection": {
                "requested_platform": "CODEX",
                "detected_capabilities": ["codex-installed"],
            },
        }
