# nWave — Experimental Channel

This source preview helps you turn a request into a result you can inspect. Use it for work where you can tolerate changes to the workflow. For a whole feature, nWave can retain decisions, a public acceptance check, review, and delivery evidence. You can also run one DES step or work directly when less needs to survive the session.

**Build:** `606700ee6` from `atdd_pure_staging` (`606700ee6a9105b6f8c2b994890d5990ffe1e085`). This channel installs from a clone of [this repository](https://github.com/nWave-ai/nWave-experimental); it does not publish to PyPI. Check the exact release receipt before using a wheel from another channel.

## Start in your project

You need Python 3.10+, Git, [uv](https://docs.astral.sh/uv/), and either [Claude Code](https://claude.com/product/claude-code) or [Codex CLI](https://developers.openai.com/codex/cli). On Windows, use WSL. Install your chosen coding host separately.

```bash
git clone https://github.com/nWave-ai/nWave-experimental.git nWave-experimental
cd nWave-experimental
uv sync
```

From the clone, install into the host you use. Choose one command:

```bash
uv run python -m nwave_ai.cli install --platform claude-code
# Or, for Codex CLI:
uv run python -m nwave_ai.cli install --platform codex
```

Use `--dev` only when you intend a development-mode installation from the checkout. For Claude Code, run `uv run python -m nwave_ai.cli doctor` in the clone and address any failing check. For Codex, check the installer's final Codex validation; `doctor` checks Claude Code assets. Quit and reopen the selected host after installation.

### Your First Command

The clone's `.venv/bin/nwave-ai` is a local executable. Bind its absolute path before moving to **your project**; `uv run` does not add `nwave-ai` to your global `PATH`.

```bash
NWAVE_CLI="$(pwd -P)/.venv/bin/nwave-ai"
cd /path/to/your/project
"$NWAVE_CLI" project enable
"$NWAVE_CLI" status
```

Check that status says `This project is active.` Open the restarted host in that project. In Claude Code, ask `/nw-buddy What should I do next?`. In Codex, invoke `$nw-buddy` and ask the same question. These are host skills, not shell commands. Then describe who uses the change, its input, and the result you expect. See [Your First Feature](docs/guides/tutorial-first-feature/) for an end-to-end example.

## Choose a delivery route

| Route | Use it when | What remains |
|---|---|---|
| Spine waves | A whole feature needs decisions and checks that outlive the session. | Durable authorities, applicable independent review, and delivery evidence. |
| Individual DES steps | You need one scoped product, design, oracle, craft, verify, or integration step. | That step's closed outcome and applicable artifacts. `NEXT` is advice, not an automatic transition. |
| Direct work | Little needs to survive the session and a late refusal is cheap. | No nWave gate, independent review, or retained authority is attested. |

The assistant and you choose the route for each request. A DES step can report `Success`, `Refusal`, `Retry`, or `Indeterminate`; treat an uncertain result as uncertain. A completed step is not a completed feature. Check the delivered behavior through its user surface. See the [route guide](docs/guides/wave-routing-and-entry-points/) and [CLI reference](docs/reference/cli.md).

## Settings, updates, and migration

Select a provider and model explicitly with the [`nw-rigor` guidance](nWave/skills/nw-rigor/SKILL.md). A competence label does not select a model automatically. [Documentation density and optional explanation](docs/reference/global-config.md#documentation-object) are separate settings; neither removes the checks required by the route you select.

Your native coding host runs the installed specialists and chooses the next action. DES constructs documents/facts, measures actual RED/GREEN, records results and performs explicitly requested native/Git operations; it never launches models. Independent review and fresh source-blind EXAMINE remain required where applicable. See the [role invocation contract](nWave/skills/nw-role-invocation/SKILL.md).

For this source preview, update the clone, resync its environment, reinstall into the same host, and restart that host. Do not replace it with a public-package upgrade. Automatic release checks and installation require separate permissions and controlled startup; the [installation guide](docs/guides/installation-guide/#controlled-startup-and-update-permissions) explains the limits. Its supported launch wrappers cover four hosts, while install and diagnostic coverage differ by host.

Coming from v3? Read the [migration guide](docs/guides/classic-spine-migration.md) before changing persisted work. A successful preview does not prove that an active v3 delivery can resume in v4. The [archived package recovery procedure](docs/guides/installation-guide/#recover-a-previous-experimental-package-identity-archive) applies only to its named predecessor and a verified release receipt.

nWave keeps workflow artifacts locally and collects no telemetry. Your coding host handles its own provider traffic; explicitly authorized external calls can send permitted data. See the [privacy policy](PRIVACY.md). Report defects through [GitHub Issues](https://github.com/nWave-ai/nWave/issues). nWave is [MIT licensed](LICENSE).
