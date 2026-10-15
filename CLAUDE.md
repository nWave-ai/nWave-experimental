<!-- BEGIN nWave-beta-section (managed by nwave-ai; do not edit) -->

## nWave (beta) — How to Work in This Project

At session start, read `~/.claude/skills/nw-typesafe-system-one/SKILL.md`
alongside these instructions. Loading alone is not use: every supported semantic question MUST use Jev when
authorized and available, with valid same-owner reuse and explicit capability
limits as defined by the skill. Confidence and predicted savings are not exemptions.
Skip this load for source-blind EXAMINE until isolated access is verified.

Three routes are open to a Request here, and they differ in what survives it.
Spine waves — the wave commands carry the gates, keep independent review and
source-blind EXAMINE where applicable, and leave durable authorities that
outlive the session; for a whole feature, evolution retains lasting facts and
FINALIZE closes the delivered work. Host-led DES steps — the native host invokes
the installed specialists; des po/design/oracle/craft/verify/integrate construct
facts and documents, measure actual RED/GREEN, record results or enact requested
native/Git effects. A public oracle exists before code. DES launches no model
and may suggest NEXT only as advice; the LLM chooses the route. Working directly — fastest, keeping no gate, no independent
review and no retained authority, so nothing attests the result.

What decides the route is what this Request has to leave behind once the
session ends, and what a late refusal would cost, since review and
integration happen once per Request.
The S/M/L size of the Request never decides the route.
For a whole feature, the spine waves are the default route here.
Working directly remains open as an answer when little has to survive;
when you take it, say so.
The LLM evaluates the Request and invokes the applicable waves.
Whichever route this Request takes, say which one.

nWave is a spine-driven delivery framework. Wave commands (`/nw-*`) carry the
gates; skills carry on-demand knowledge; agents execute. This section is an
INDEX — it tells you which to reach for, not how each one works internally.

Human authority decides only genuine scope or trade-offs.

| User wants... | Load / run |
|---|---|
| Validate a problem is real | `/nw-discover` |
| Compare solution directions | `/nw-diverge` |
| Clarify jobs, journeys, outcomes | `/nw-discuss` |
| Architecture, reuse, boundaries | `/nw-design` |
| Deployment / operational constraints | `/nw-devops` |
| Executable public oracle | `/nw-distill` |
| Dispatch one Request | `/nw-deliver` |
| Fix one observed defect | `/nw-bugfix` |
| Review an artifact or diff | `/nw-review` |
| Reduce a noisy test suite | `/nw-optimize-tests` |
| Explicit mutation probe | `/nw-mutation-test` |
| Resume after an interruption | `des state --repo-root "$(pwd -P)"` from the repository root (where the Request stands; `NEXT` is advisory) |
| Decide how big a Request is, and when to ask the human | skill `nw-auto` |
| Anything else — methodology, routing, "what do I do" | skill `nw-buddy` |

**Batch independent tool calls in one turn; sequence only when one result determines the next input.**

### Asking the User a Question

Fixed shape, every time: **context** -> **recommendation** -> **options** (each
with its consequence/risk) -> one direct question. Real section headers and
bold labels — never a wall of text. User-facing output follows **ASD-STE100**
(Simplified Technical English).

### Communication

<!-- GENERATED:communication-rules START — source of truth: des.adapters.driven.config.des_config.DESConfig.effective_config() (ADR-CFG-001 Slice 2 -- ~/.nwave/config.json + .nwave/config.json); do not hand-edit (docgen renders this region) -->
- Communication verbosity: **standard**
- Commit attribution: **enabled**
<!-- GENERATED:communication-rules END -->

### Privacy — Non-Negotiable

nWave stores workflow data locally and collects no telemetry. Explicitly authorized Jev questions use a remote service; credential presence alone is not authorization ([PRIVACY.md](../../PRIVACY.md)). Feedback via GitHub Issues is welcome, never required.

<!-- END nWave-beta-section -->
