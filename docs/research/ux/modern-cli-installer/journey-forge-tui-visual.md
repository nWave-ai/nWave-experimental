# Journey: Forge Build + Install TUI Redesign

## Visual Design System

### 1. Color Semantics (Minimal Palette)

| Color   | Semantic          | Rich Markup           | Usage                              |
|---------|-------------------|-----------------------|------------------------------------|
| Green   | Success/Pass      | `[green]`             | Passed checks, success messages    |
| Red     | Error/Fail/Block  | `[red]`               | Failed checks, blocking errors     |
| Yellow  | Warning           | `[yellow]`            | Non-blocking warnings              |
| Dim     | Secondary info    | `[dim]`               | Paths, sizes, durations, details   |
| Bold    | Primary content   | `[bold]`              | Version numbers, package names     |
| Default | Body text         | (no markup)           | Normal flowing text                |

**Rule**: Colors ONLY for pass/warn/fail semantics. Never decorative. Let emoji do the emotional work.

### 2. Emoji Vocabulary (Structured with Spark)

| Emoji | Meaning                | Context                         |
|-------|------------------------|---------------------------------|
| `🔨`  | Building               | Build phase header              |
| `📦`  | Packaging/Installing   | Install phase header            |
| `✅`  | Step passed/completed  | Completed check or phase        |
| `⚠️`   | Warning (non-blocking) | Warning checks (git dirty, etc) |
| `❌`  | Failed/Blocked         | Blocking failure                |
| `🔍`  | Checking/Verifying     | Pre-flight, verification        |
| `💾`  | Backup                 | Backup phase                    |
| `⚙️`  | Active operation       | Install-in-progress section     |
| `📋`  | Manifest/inventory     | SBOM "what was installed"       |
| `🩺`  | Health check           | Post-install verification       |
| `🎉`  | Celebration            | Final success moment ONLY       |
| `→`   | Version transition     | Version bump, install path      |

**Rule**: One emoji per line, always at the start. No emoji soup. Each emoji has exactly one meaning.

### 3. Typography Rules

| Element          | Style           | Example                                    |
|------------------|-----------------|--------------------------------------------|
| Phase header     | Bold + emoji    | `🔨 Building crafter-ai`                   |
| Check result     | Emoji + text    | `  ✅ pyproject.toml found`                |
| Summary label    | Bold            | `Version: 0.2.0`                           |
| Secondary detail | Dim             | `(104.1 KB, 3.04s)`                        |
| Section spacing  | 1 blank line    | Between phases, never inside               |
| Indent           | 2 spaces        | Check items under phase headers             |

**Rule**: No borders, no boxes, no panels, no tables, no horizontal rules, no `===` lines. Ever.

### 4. Spacing and Rhythm

```
[blank line]
Phase header (bold + emoji)
  Check line 1
  Check line 2
  Check line 3
  Phase summary line
[blank line]
Next phase header
```

- One blank line between phases
- Two-space indent for items within a phase
- No trailing blank lines within a phase
- The output reads like a well-formatted log, top to bottom


---

## Screen-by-Screen Mockups: Happy Path

### Full Build + Install Flow (continuous)

```
🔨 Building crafter-ai

  🔍 Pre-flight checks
  ✅ pyproject.toml found
  ✅ Build toolchain ready
  ✅ Source directory found
  ⚠️  Uncommitted changes detected
  ✅ Version available for release
  ✅ Pre-flight passed

  📐 Version
  0.1.0 → 0.2.0 (minor)

  ⏳ Compiling wheel...                    ← spinner (animated, replaces itself)
  ✅ Wheel built (1.2s)                    ← spinner resolves to this line

  🔍 Validating wheel
  ✅ PEP 427 format valid
  ✅ Metadata complete
  ✅ Wheel validated

  ⚙️ Building IDE bundle
  ⏳ Processing nWave assets...             ← spinner (animated during ~5.2s build)
  ✅ IDE bundle built (5.2s)                ← spinner resolves
    30 agents, 23 commands, 0 teams         ← dim detail: component counts
    3 embed injections applied              ← dim detail: DES embeds processed
    ⚠️  4 YAML warnings (non-blocking)       ← only shown when warnings exist
      documentarist-reviewer: YAML parse error  ← dim detail: file + reason
      documentarist: YAML parse error
      illustrator-reviewer: no YAML config block
      illustrator: no YAML config block

  🔨 Build complete
    crafter_ai-0.2.0-py3-none-any.whl      ← dim detail: wheel artifact
    IDE bundle: 30 agents, 23 commands      ← dim detail: IDE bundle artifact

📦 Install crafter-ai 0.2.0? [Y/n]: y

📦 Installing crafter-ai

  🔍 Pre-flight checks
  ✅ Wheel file found
  ✅ Wheel format valid
  ✅ pipx environment ready
  ✅ Install path writable
  ✅ IDE bundle found (30 agents, 23 commands)  ← NEW check
  ✅ Pre-flight passed

  💾 Backing up configuration
  ⏳ Creating backup...                    ← spinner
  ✅ Backup saved (0.3s)                   ← spinner resolves
    agents, commands, templates, scripts, manifest, install log, DES, settings, CLAUDE.md → ~/.claude/backups/nwave-install-20260204-192001

  ⚙️ Installing CLI
  ⏳ Installing via pipx...                ← spinner (animated during ~3s pipx install)
  ✅ nWave CLI installed via pipx (2.9s)   ← spinner resolves to closure line

  ⚙️ Deploying nWave assets
  ⏳ Installing to ~/.claude/...           ← spinner (animated during asset copy)
  ✅ Assets deployed (0.8s)                ← spinner resolves
    30 agents → ~/.claude/agents/nw/
    23 commands → ~/.claude/commands/nw/
    17 templates → ~/.claude/templates/
    4 scripts → ~/.claude/scripts/

  🔍 Validating deployment
  ✅ Agents verified (30)
  ✅ Commands verified (23)
  ✅ Templates verified (17)
  ✅ Scripts verified (4)
  ✅ Manifest created
  ✅ Schema validated (v3.0, 7 phases)
  ✅ Deployment validated

  📋 What was installed
    crafter-ai 0.2.0
    CLI: crafter-ai, nw
    → ~/.local/pipx/venvs/crafter-ai

    30 agents → ~/.claude/agents/nw/
    23 commands → ~/.claude/commands/nw/
    17 templates → ~/.claude/templates/
    4 scripts → ~/.claude/scripts/
    1 config → ~/.claude/agents/nw/config.json
    1 manifest → ~/.claude/nwave-manifest.txt

  🩺 Verifying installation
  ✅ CLI responds to --version
  ✅ Core modules loadable
  ✅ nWave assets accessible                ← NEW: verifies deployed assets
  ✅ Health: HEALTHY

🎉 nWave 0.2.0 installed and healthy!
   Ready to use in Claude Code.

  📖 Getting started
    /nw:discuss  - Requirements gathering and business analysis
    /nw:design   - Architecture design with visual representation
    /nw:distill  - Acceptance test creation and business validation
    /nw:develop  - Outside-In TDD implementation with refactoring
    /nw:deliver  - Production readiness validation

  🆕 What's new in 0.2.0                   ← only shown when changelog exists
    Unified build + install pipeline
    IDE bundle with asset deployment
```

### Key Design Decisions Explained

**Phase headers** (`🔨 Building crafter-ai`, `📦 Installing crafter-ai`)
use bold text and a tool emoji. They establish WHERE you are in the journey.

**Check lines** are indented 2 spaces with a status emoji. Each reads as a
complete sentence fragment: `✅ pyproject.toml found`. No labels, no columns,
no "Check: ... Status: ... Details: ..." structure.

**Spinners** appear as `⏳ Compiling wheel...` and when the operation completes,
the spinner line is REPLACED (Rich `console.status`) with the persistent result
line: `✅ Wheel built (1.2s)`. The key insight: the spinner uses `console.status()`
which replaces itself, but we ALSO print the completed line AFTER stopping the
spinner, so the result persists in stdout.

**The version line** is minimal: `0.1.0 → 0.2.0 (minor)`. No panel, no box.
Just the information.

**The IDE bundle build** (`⚙️ Building IDE bundle`) is a new phase that
processes the nWave source directory into the IDE-compatible distribution at
`dist/ide/`. It shows component counts (30 agents, 23 commands, 0 teams),
DES embed injection count (3), and YAML warnings (4, non-blocking) with per-file detail.
The spinner runs during the ~5.2-second build. This phase is critical because
it produces the asset bundle that gets deployed to `~/.claude/` during install.

**The build complete** is now a sub-phase header with TWO dim detail lines:
one for the wheel artifact and one for the IDE bundle. The build now produces
two artifacts, and both must be visible so the user knows what was built
before being asked to install.

**The confirmation prompt** appears between build and install as a natural
decision point: `📦 Install crafter-ai 0.2.0? [Y/n]: y`. The `📦` emoji
signals we are transitioning to the install phase. Default is yes (capital Y).
No box, no panel. Just a prompt in the flow. When the user confirms, the
install phase header follows immediately.

**The install pre-flight** now includes a check for the IDE bundle:
`✅ IDE bundle found (30 agents, 23 commands)`. This catches the case where
someone runs `forge install` without having built the IDE bundle first.

**The backup section** (upgrade path) now backs up the full ~/.claude/ scope:
agents, commands, templates, scripts, manifest, install log, DES modules,
settings files, and CLAUDE.md. The dim detail line shows the complete list
with the backup destination path.

**CLI Installation** (renamed from "Installing") uses `⚙️ Installing CLI`
to distinguish from asset deployment. The spinner runs during the ~3-second
pipx install. The closure line uses "nWave CLI" to clarify this is the CLI
package, not the full asset set.

**Asset Deployment** (`⚙️ Deploying nWave assets`) is a new section that
copies the IDE bundle contents to `~/.claude/`. It shows four dim detail
lines with arrow notation: `30 agents → ~/.claude/agents/nw/`, etc. This
replaces what `install_nwave.py` does with Rich panels and tables.

**Deployment Validation** (`🔍 Validating deployment`) replaces the Rich
bordered table from `install_nwave.py` with an emoji stream. Each component
category gets a verification line with count. The manifest and schema
validation are also shown here. No table borders anywhere.

**The SBOM manifest** (`📋 What was installed`) is now split into two groups
separated by a blank line: CLI package (what pipx installed) and IDE assets
(what went to `~/.claude/`). Every component category is listed with count
and destination. Nothing is compressed. The six IDE asset categories are:
agents, commands, templates, scripts, config, and manifest.

**The health verification** now includes `✅ nWave assets accessible` to
verify that the deployed assets in `~/.claude/` are readable by Claude Code.

**The celebration** starts with the `🎉` line (the emotional peak), then
"Ready to use in Claude Code" as the bridge to action. The `📖 Getting started`
section always shows the available /nw: commands so users know what they can do.
For upgrades, a conditional `🆕 What's new` section highlights important changes
when a changelog entry exists for this version. This replaces the old Rich panel
that dumped all commands in a box.


### Fresh Install Variant

When no previous version exists, the backup section is a single informational
line (no spinner needed, nothing to back up):

```
📦 Installing crafter-ai

  🔍 Pre-flight checks
  ✅ Wheel file found
  ✅ Wheel format valid
  ✅ pipx environment ready
  ✅ Install path writable
  ✅ IDE bundle found (30 agents, 23 commands)
  ✅ Pre-flight passed

  💾 Fresh install, no backup needed

  ⚙️ Installing CLI
  ⏳ Installing via pipx...                ← spinner (animated during ~3s pipx install)
  ✅ nWave CLI installed via pipx (2.9s)   ← spinner resolves to closure line

  ⚙️ Deploying nWave assets
  ⏳ Installing to ~/.claude/...           ← spinner (animated during asset copy)
  ✅ Assets deployed (0.8s)                ← spinner resolves
    30 agents → ~/.claude/agents/nw/
    23 commands → ~/.claude/commands/nw/
    17 templates → ~/.claude/templates/
    4 scripts → ~/.claude/scripts/

  🔍 Validating deployment
  ✅ Agents verified (30)
  ✅ Commands verified (23)
  ✅ Templates verified (17)
  ✅ Scripts verified (4)
  ✅ Manifest created
  ✅ Schema validated (v3.0, 7 phases)
  ✅ Deployment validated

  📋 What was installed
    crafter-ai 0.2.0
    CLI: crafter-ai, nw
    → ~/.local/pipx/venvs/crafter-ai

    30 agents → ~/.claude/agents/nw/
    23 commands → ~/.claude/commands/nw/
    17 templates → ~/.claude/templates/
    4 scripts → ~/.claude/scripts/
    1 config → ~/.claude/agents/nw/config.json
    1 manifest → ~/.claude/nwave-manifest.txt

  🩺 Verifying installation
  ✅ CLI responds to --version
  ✅ Core modules loadable
  ✅ nWave assets accessible
  ✅ Health: HEALTHY

🎉 nWave 0.2.0 installed and healthy!
   Ready to use in Claude Code.

  📖 Getting started
    /nw:discuss  - Requirements gathering and business analysis
    /nw:design   - Architecture design with visual representation
    /nw:distill  - Acceptance test creation and business validation
    /nw:develop  - Outside-In TDD implementation with refactoring
    /nw:deliver  - Production readiness validation
```

Note: For fresh installs, the backup section is a single informational line
(no spinner needed, nothing to back up). Asset deployment and the SBOM
always show the full inventory regardless of install type, because the
unified installer always deploys all assets to `~/.claude/`.


---

## Error State Mockups

### Blocking Pre-flight Failure (Build)

```
🔨 Building crafter-ai

  🔍 Pre-flight checks
  ❌ pyproject.toml not found
  ✅ Build toolchain ready
  ❌ Source directory not found
  ⚠️  Uncommitted changes detected
  ✅ Version available for release

  Build blocked: 2 checks failed

  ❌ pyproject.toml not found
     Fix: Create pyproject.toml in project root
     See: https://packaging.python.org/en/latest/guides/writing-pyproject-toml/

  ❌ Source directory not found
     Fix: Create a src/ directory with your package structure
```

**Design decisions for errors**:
- All checks still run and display (user sees the full picture)
- A summary line counts failures: `Build blocked: 2 checks failed`
- Then ONLY the failures are repeated with remediation details
- Remediation is indented under the failure with `Fix:` label
- URLs are on a separate `See:` line (keeps lines scannable)
- No red boxes. No panels. Just clear, actionable text.

### Blocking Pre-flight Failure (Install)

```
📦 Installing crafter-ai

  🔍 Pre-flight checks
  ❌ No wheel file found in dist/
  ❌ pipx is not installed
  ✅ Install path writable
  ❌ IDE bundle not found in dist/ide/

  Install blocked: 3 checks failed

  ❌ No wheel file found in dist/
     Fix: Run 'crafter-ai forge build' first

  ❌ pipx is not installed
     Fix: pip install pipx && pipx ensurepath

  ❌ IDE bundle not found in dist/ide/
     Fix: Run 'crafter-ai forge build' to generate the IDE bundle
```

### IDE Bundle Build Failure

```
🔨 Building crafter-ai

  ...pre-flight and wheel build as normal...

  ⚙️ Building IDE bundle
  ⏳ Processing nWave assets...
  ❌ IDE bundle build failed

  Error: nWave/ source directory is missing or empty
  Fix: Ensure nWave/ directory exists with agent and command source files
```

### Asset Deployment Failure

```
📦 Installing crafter-ai

  ...pre-flight, backup, and CLI install as normal...

  ⚙️ Deploying nWave assets
  ⏳ Installing to ~/.claude/...
  ❌ Asset deployment failed

  Error: Permission denied writing to ~/.claude/agents/nw/
  Fix: Check write permissions on ~/.claude/ directory
```

### Deployment Validation Failure

```
📦 Installing crafter-ai

  ...pre-flight through asset deployment as normal...

  🔍 Validating deployment
  ✅ Agents verified (30)
  ❌ Commands verification failed (expected 23, found 21)
  ✅ Templates verified (17)
  ✅ Scripts verified (4)

  Deployment validation failed: 1 check failed

  ❌ Commands verification failed (expected 23, found 21)
     Fix: Re-run 'crafter-ai forge install' or check ~/.claude/commands/nw/
```

### Build Failure (compilation error)

```
🔨 Building crafter-ai

  🔍 Pre-flight checks
  ✅ pyproject.toml found
  ✅ Build toolchain ready
  ✅ Source directory found
  ✅ Git status clean
  ✅ Version available for release
  ✅ Pre-flight passed

  📐 Version
  0.1.0 → 0.2.0 (minor)

  ⏳ Compiling wheel...
  ❌ Build failed

  Error: Invalid package metadata in pyproject.toml
  Fix: Check [project] section in pyproject.toml
```

### Install Failure (pipx error)

```
📦 Installing crafter-ai

  🔍 Pre-flight checks
  ✅ Wheel file found
  ✅ Wheel format valid
  ✅ pipx environment ready
  ✅ Install path writable
  ✅ Pre-flight passed

  💾 Backing up configuration
  ⏳ Creating backup...
  ✅ Backup saved (0.3s)
    agents, commands, templates, scripts, manifest, install log, DES, settings, CLAUDE.md → ~/.claude/backups/nwave-install-20260204-192001

  ⚙️ Installing CLI
  ⏳ Installing via pipx...
  ❌ Installation failed

  Error: pipx install failed: dependency conflict
  Fix: Try 'pipx install --force' or check dependency versions
```

### Degraded Health (post-install warning)

```
📦 Installing crafter-ai

  ...checks and install as normal...

  🩺 Verifying installation
  ✅ CLI responds to --version
  ⚠️  Some optional modules not found
  ✅ Health: DEGRADED

⚠️  crafter-ai 0.2.0 installed with warnings
   Some features may be limited. Run 'crafter-ai doctor' for details.
```

Note: When health is DEGRADED, the celebration downgrades from `🎉` to `⚠️`
and the message is honest but not alarming. The tool is usable.


---

## Interaction Patterns

### Pattern 1: Spinner to Persistent Line

```python
# BEFORE (current - line disappears)
with console.status("Installing..."):
    result = do_install()
# Nothing persists in stdout

# AFTER (new design - line persists)
status = console.status("⏳ Installing via pipx...")
status.start()
result = do_install()
status.stop()
console.print("📦 Installed via pipx (3.04s)")  # This line PERSISTS
```

The key: after `status.stop()`, print the completed result as a normal line.
The spinner vanishes, but the result line stays forever in the scrollback.

### Pattern 2: Check List Display

```python
# Print each check as it completes (streaming feel)
for check in results:
    if check.passed:
        if check.severity == CheckSeverity.WARNING:
            # Passed warning-level checks still show as success
            console.print(f"  ✅ {check.message}")
        else:
            console.print(f"  ✅ {check.message}")
    elif check.severity == CheckSeverity.WARNING:
        console.print(f"  ⚠️  {check.message}")
    else:
        console.print(f"  ❌ {check.message}")
```

### Pattern 3: Phase Header

```python
console.print()  # blank line before phase
console.print(f"[bold]🔨 Building crafter-ai[/bold]")
```

No panel. No box. Bold text with emoji. That's it.

### Pattern 4: Confirmation Prompt

```
📦 Install crafter-ai 0.2.0? [Y/n]:
```

One line. Emoji matches the phase. Default is yes (capital Y).
No box around it. Flows naturally in the stream.

### Pattern 5: Celebration Moment

```python
console.print()
if health_status == "HEALTHY":
    console.print(f"[bold green]🎉 nWave {version} installed and healthy![/bold green]")
    console.print("[dim]   Ready to use in Claude Code.[/dim]")
elif health_status == "DEGRADED":
    console.print(f"[bold yellow]⚠️  nWave {version} installed with warnings[/bold yellow]")
    console.print("[dim]   Some features may be limited. Run 'crafter-ai doctor' for details.[/dim]")
```

The celebration is the ONLY place where the full line is colored (green for
healthy, yellow for degraded). Everywhere else, only the emoji carries emotion.
Note: Uses "nWave" (product brand) not "crafter-ai" (package name).

### Pattern 6: Error Detail Block

```python
# After the check list, if there are blocking failures:
console.print()
console.print(f"[red]  Build blocked: {count} checks failed[/red]")
console.print()
for failure in blocking_failures:
    console.print(f"  [red]❌ {failure.message}[/red]")
    if failure.remediation:
        console.print(f"[dim]     Fix: {failure.remediation}[/dim]")
```

Errors are shown in red. Remediation is dim (secondary information).
Indentation creates visual hierarchy without borders.

### Pattern 7: Sub-phase with Spinner and Detail

Used for operations that have a section header, a spinner during work,
a closure line, and optional detail lines afterward.

```python
# Backup section (upgrade path)
console.print()
console.print("  💾 Backing up configuration")
status = console.status("  ⏳ Creating backup...")
status.start()
backup_result = do_backup()
status.stop()
console.print(f"  ✅ Backup saved ({duration})")
console.print(f"[dim]    {backed_up_items} → {backup_result.backup_path}[/dim]")

# CLI Install section
console.print()
console.print("  ⚙️ Installing CLI")
status = console.status("  ⏳ Installing via pipx...")
status.start()
install_result = do_install()
status.stop()
console.print(f"  ✅ nWave CLI installed via pipx ({duration})")

# Asset Deployment section
console.print()
console.print("  ⚙️ Deploying nWave assets")
status = console.status("  ⏳ Installing to ~/.claude/...")
status.start()
deploy_result = deploy_assets()
status.stop()
console.print(f"  ✅ Assets deployed ({duration})")
console.print(f"[dim]    {agent_count} agents → ~/.claude/agents/nw/[/dim]")
console.print(f"[dim]    {command_count} commands → ~/.claude/commands/nw/[/dim]")
console.print(f"[dim]    {template_count} templates → ~/.claude/templates/[/dim]")
console.print(f"[dim]    {script_count} scripts → ~/.claude/scripts/[/dim]")
```

The section header (💾 or ⚙️) names the operation. The spinner provides
active feedback. The closure line (✅) confirms completion. Detail lines
(dim, 4-space indent) provide supporting information.

### Pattern 8: SBOM Manifest Display

Shows what was installed, using dim text at 4-space indent. No emojis on
individual manifest lines; they are informational, not status indicators.

```python
# After deployment validation
console.print()
console.print("  📋 What was installed")
# CLI package group
console.print(f"[dim]    {package_name} {version}[/dim]")
console.print(f"[dim]    CLI: {', '.join(entry_points)}[/dim]")
console.print(f"[dim]    → {install_path}[/dim]")
console.print()  # blank line separates CLI from IDE assets
# IDE assets group
console.print(f"[dim]    {agent_count} agents → ~/.claude/agents/nw/[/dim]")
console.print(f"[dim]    {command_count} commands → ~/.claude/commands/nw/[/dim]")
console.print(f"[dim]    {template_count} templates → ~/.claude/templates/[/dim]")
console.print(f"[dim]    {script_count} scripts → ~/.claude/scripts/[/dim]")
console.print(f"[dim]    1 config → ~/.claude/agents/nw/config.json[/dim]")
console.print(f"[dim]    1 manifest → ~/.claude/nwave-manifest.txt[/dim]")
```

The manifest answers "what just happened to my system?" and builds trust.
It is split into two groups: CLI package (what pipx installed) and IDE assets
(what went to `~/.claude/`). The `→` notation shows destination paths.
Every component category is listed; nothing is compressed or omitted.


---

## Anti-Patterns: What to NEVER Do

### 1. NO Tables for Sequential Data

```
WRONG:
┏━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Check         ┃ Status ┃ Details                  ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ pyproject.toml│   ✓    │ Found                    │
└───────────────┴────────┴─────────────────────────┘

RIGHT:
  ✅ pyproject.toml found
```

Tables add friction. Every border character is noise. The CLI is sequential;
the output should be sequential.

### 2. NO Panels or Boxes for Simple Messages

```
WRONG:
╭───────────── Build Summary ─────────────╮
│ FORGE: BUILD COMPLETE                    │
│ Wheel: crafter_ai-0.2.0-py3-none-any.whl│
│ Version: 0.2.0                           │
╰──────────────────────────────────────────╯

RIGHT:
🔨 Build complete: crafter_ai-0.2.0-py3-none-any.whl
```

One line. Contains everything you need. No visual overhead.

### 3. NO Vanishing Spinners

```
WRONG:
with console.status("Installing..."):
    do_install()
# Spinner vanishes. No trace it ever ran. User wonders "did it work?"

RIGHT:
spinner.start()
do_install()
spinner.stop()
console.print("📦 Installed via pipx (3.04s)")
# Result persists in terminal scrollback forever
```

### 4. NO Mixed Visual Languages

```
WRONG:
╭─── Version Analysis ───╮   ← Rich Panel
┏━━━━━━━━━┳━━━━━━━━━━━━━┓  ← Rich Table
============ COMPLETE ====  ← ASCII block
---                         ← Markdown rule

RIGHT:
Every section uses the same pattern:
  Emoji + text for items
  Bold for headers
  Dim for details
```

### 5. NO Redundant Labels

```
WRONG:
  Check: Pyproject.toml Exists   Status: ✓   Details: pyproject.toml found

RIGHT:
  ✅ pyproject.toml found
```

The emoji IS the status. The text IS the detail. The check name is
implied by the message. Three columns compressed to one clear line.

### 6. NO "FORGE:" Prefix Shouting

```
WRONG:
FORGE: BUILD COMPLETE
FORGE: INSTALL COMPLETE

RIGHT:
🔨 Build complete: crafter_ai-0.2.0-py3-none-any.whl
🎉 crafter-ai 0.2.0 installed and healthy!
```

The tool name is in the command the user typed. No need to shout it back.

### 7. NO Information Dump in Celebration

```
WRONG:
  Version:       0.2.0
  Install Path:  /Users/mike/.local/bin
  Wheel:         crafter_ai-0.2.0-py3-none-any.whl
  Wheel Size:    104.1 KB (106622 bytes)
  Duration:      3.04s
  Phases:        5 completed
  Health Status: HEALTHY

RIGHT:
🎉 crafter-ai 0.2.0 installed and healthy!
   Ready to use in Claude Code.
```

The celebration is a FEELING, not a report. Version + health is the signal.
Everything else is noise at this moment. The user wants the "wow", not a receipt.


---

## Emotional Arc

```
Phase                    Emotion              Visual Signal
──────────────────────────────────────────────────────────────
Start                    Anticipation         🔨 bold header
Pre-flight checks        Building confidence  ✅ ✅ ✅ rapid green
Warning (if any)         Brief attention       ⚠️  acknowledged, moves on
Version display          Clarity              Clean, simple line
Build spinner            Tension/waiting      ⏳ animated dots
Wheel validation         Confidence           ✅ ✅ format checks pass
IDE bundle build         Second tension       ⏳ ~5.2s spinner, embed injections
Build complete           Relief               🔨 two artifacts confirmed
Install prompt           Decision moment      📦 user confirms, feels in control
Install header           Momentum continues   📦 seamless transition
Install checks           Confidence again     ✅ ✅ ✅ ✅ ✅ more green (IDE bundle check)
Backup (upgrade)         Safety/trust         💾 your data is safe, spinner + detail
Backup (fresh)           Acknowledged         💾 brief line, nothing to worry about
CLI install spinner      Peak tension         ⏳ active feedback during ~3s pipx wait
CLI install closure      Relief               ✅ nWave CLI installed, with timing
Asset deployment         Second peak tension  ⏳ deploying to ~/.claude/
Deploy detail lines      Transparency         dim arrows showing what went where
Deployment validation    Growing trust        ✅ ✅ ✅ ✅ ✅ ✅ ✅ all verified
SBOM manifest            Full transparency    📋 complete BOM: CLI + IDE assets
Health verification      Final validation     🩺 professional care, asset check
CELEBRATION              Peak joy             🎉 THE moment. Bold green.
```

The user's journey: Anticipation, growing confidence, brief tension during
compilation, a second tension during IDE bundle processing, then transparent
two-phase installation (CLI via pipx, assets to `~/.claude/`), followed by
validation and a complete bill of materials. The resolution is clear, warm,
and satisfying.

The critical emotional gaps that were fixed:
1. The 3-second silence during pipx install (spinner provides active feedback)
2. The invisible asset deployment (now visible with component counts and destinations)
3. The Rich table validation (replaced with emoji stream matching the design system)
4. The compressed SBOM (now shows every component category with counts and paths)
Together they transform a suspicious black-box operation into a transparent,
confidence-building experience where the user sees exactly what was deployed
and where.


---

## Shared Artifacts

| Artifact           | Source of Truth               | Appears In                                                              |
|--------------------|-------------------------------|-------------------------------------------------------------------------|
| `version`          | Wheel METADATA (canonical)    | Version line, prompt, build complete, SBOM manifest, celebration        |
| `package_name`     | `pyproject.toml`              | Phase headers, wheel name, SBOM manifest                                |
| `product_name`     | Hardcoded: "nWave"            | CLI install closure line, celebration message                           |
| `wheel_name`       | Build output                  | Build complete detail line                                              |
| `agent_count`      | IDE bundle build output       | IDE bundle detail, build complete, install pre-flight, deploy, validation, SBOM |
| `command_count`    | IDE bundle build output       | IDE bundle detail, build complete, install pre-flight, deploy, validation, SBOM |
| `template_count`   | Post-deploy scan ~/.claude    | Deploy detail, validation, SBOM                                         |
| `script_count`     | Post-deploy scan ~/.claude    | Deploy detail, validation, SBOM                                         |
| `team_count`       | IDE bundle build output       | IDE bundle detail (shows 0 when dir missing)                            |
| `embed_count`      | IDE bundle build output       | IDE bundle detail                                                       |
| `schema_version`   | TDD cycle schema JSON         | Deployment validation                                                   |
| `schema_phases`    | TDD cycle schema JSON         | Deployment validation                                                   |
| `deploy_target`    | Hardcoded: "~/.claude/"       | Deploy detail lines, SBOM asset lines                                   |
| `install_path`     | pipx list_packages()          | SBOM manifest (CLI install location)                                    |
| `cli_entry_points` | Wheel METADATA entry_points   | SBOM manifest (CLI commands registered)                                 |
| `backup_path`      | BackupResult.backup_path      | Backup detail line                                                      |
| `health_status`    | HealthChecker                 | Verification line, celebration message tone                             |
| `duration`         | Timer                         | Spinner resolution lines                                                |

**Version data flow** (single canonical path, no ambiguity):
```
pyproject.toml → build process → wheel METADATA → all displays
```
The version displayed in the build summary, the install prompt, the SBOM
manifest, and the celebration MUST all come from the same
`InstallResult.version` value, which is parsed from the wheel's METADATA
file. There is no "or". The wheel metadata is the single source of truth
because that is what the user will actually get when they install the package.

**Component count data flow** (build to install to SBOM):
```
nWave/ source → IDE bundle build → dist/ide/ → install pre-flight check
dist/ide/ → asset deployer → ~/.claude/ → deploy validation → SBOM
```
Agent and command counts originate from the IDE bundle build (30 agents,
23 commands) and flow through pre-flight, deployment, validation, and SBOM.
Template and script counts come from a post-deploy scan of `~/.claude/`.
All six SBOM display points must show consistent counts.

**Deploy target consistency**: The `~/.claude/` path is hardcoded in the
deploy detail lines and SBOM asset lines. A mismatch means the SBOM lies
about where files went. A single constant is required.

**Product name vs package name**: The celebration and install closure use
"nWave" (the product brand), while the package identity in the SBOM uses
"crafter-ai" (the PyPI package name). This is intentional: "nWave" is what
the user thinks they installed; "crafter-ai" is the technical package name
that pipx and pip use.

**SBOM data sources** (what needs to be gathered post-install):
```
pipx install result → version, success
pipx list --json    → install_path (venv path)
wheel METADATA      → entry_points (CLI commands: crafter-ai, nw)
IDE bundle build    → agent_count, command_count (from dist/ide/)
~/.claude/ scan     → template_count, script_count (post-deploy)
~/.claude/ files    → config.json exists, manifest exists
```
The SBOM always shows the full inventory for both fresh and upgrade installs,
because the unified installer always deploys all assets to `~/.claude/`.
