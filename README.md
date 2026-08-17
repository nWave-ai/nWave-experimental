# nWave — Experimental Channel

> Experimental software: breaking changes are expected. Evaluate it on
> non-critical work and report concrete friction or defects.

**Build:** `bd668ec` from `feature/atdd-pure-staging` (`bd668ec7da0e77d4fe35ca1a516a522bb3715194`)

## What nWave does

nWave turns product value and permanent architecture decisions into a minimal
executable oracle, an immutable `DeliveryContract`, test-driven implementation,
independent user-surface observation and one terminal cleanup. It aims to keep
the structural quality of disciplined software delivery while approaching the
time, token and monetary cost of an unstructured coding session.

The upstream waves remain available when their questions are genuinely open:

`DISCOVER → DIVERGE → DISCUSS → DESIGN → DEVOPS → DISTILL → DELIVER`

The minimum delivery floor is DISTILL → DELIVER. Auto and Human routes share
the same authorities and quality floor; they differ only in interaction
cadence. A small, self-contained task may take the direct route after explicit
mode and size selection.

## Thin delivery model

- Existing product and architecture documents remain their own permanent
  authorities; nWave does not copy them into a progress file.
- DISTILL produces or binds one executable oracle and one schema-valid
  `DeliveryContract`.
- DELIVER implements that contract through the repository-native runner.
- When `applicability.examine=true`, a source-blind examiner walks every valid
  expectation charter once through the public surface.
- Finalize is internal to the live delivery: it runs once and commits exactly
  `AuthorizedDeliveryPaths`. F then performs clean-checkout closure;
  pre-existing user-owned paths are untouched.

No feature-delta, completion ledger, standing-loop controller or mutable
workflow state is part of this model.

Useful provider-neutral commands:

```bash
des validate-delivery-contract --repo-root /absolute/repo --delivery-contract path/to/contract.json
des dispatch --repo-root /absolute/repo --delivery-contract path/to/contract.json
des charter-scaffold --delivery-id delivery-id --value "observable value" --repo-root /absolute/repo
des verify-charter-filled --charter docs/product/expectations/delivery-id/intent.md
des code-fact --help
```

## Install

Prerequisites: Python 3.10+ and either `uv` or `pipx`.

```bash
git clone https://github.com/nWave-ai/nWave-experimental.git
cd nWave-experimental
uv run python -m nwave_ai.cli install
```

Restart the host after installation. Enable nWave only in a project where you
want its managed guidance:

```bash
cd /path/to/project
nwave-ai project enable
```

Disable it without touching user-owned guidance:

```bash
nwave-ai project disable
```

Uninstall globally with:

```bash
uv run python -m nwave_ai.cli uninstall
```

## Parallel work and feedback

Independent analysis and authoring may use isolated worktrees. Heavy local
verification remains bounded so parallel lanes do not make the workstation
unresponsive. A worktree is reconciled and removed after integration; it is
never a durable project archive.

nWave sends no telemetry. Share feedback manually through
[the experimental issue tracker](https://github.com/nWave-ai/nWave-experimental/issues),
after removing project content, credentials and identifying details.

This channel is installed from the clone and is not published to PyPI.
