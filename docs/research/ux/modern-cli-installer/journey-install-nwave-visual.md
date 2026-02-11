# Journey: Install nWave for the First Time

**Designer**: Luna (leanux-designer)
**Date**: 2026-01-31
**Epic**: modern_CLI_installer
**Emotional Arc**: Excited → Delighted (amplify, don't dampen)

---

## Journey Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│   USER GOAL: Install nWave and verify it works in Claude Code              │
│                                                                             │
│   Trigger: Saw demo/conference talk, excited to try it                      │
│   Success: Claude powered by nWave, ready to use /nw: commands             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Step 1: Entry Point

```
┌─ Step 1: Run Installation Command ─────────────────────────┐  Emotion: Excited
│                                                            │  "Can't wait to
│  $ pipx install nwave                                      │   try this!"
│                                                            │
│  (User found this command in README or conference slide)   │
│                                                            │
└────────────────────────────────────────────────────────────┘
          │
          │ If pipx not found...
          ▼
┌─ Error: pipx Not Found ────────────────────────────────────┐  Emotion: Blocked
│                                                            │  "Oh, I need
│  ✗ pipx not found                                         │   something first"
│                                                            │
│  nWave requires pipx for isolated installation.            │
│  Install it first:                                         │
│                                                            │
│    pip install pipx                                        │
│    pipx ensurepath                                         │
│                                                            │
│  Then run: pipx install nwave                             │
│                                                            │
└────────────────────────────────────────────────────────────┘
          │
          │ User installs pipx, retries
          ▼
```

---

## Step 2: Download Phase

```
┌─ Step 2: Downloading nWave ────────────────────────────────┐  Emotion: Anticipation
│                                                            │  "It's happening!"
│  Downloading nWave...                                      │
│                                                            │
│  ████████████████████████░░░░░░░░ 75%                     │
│  nwave-${version}.tar.gz ◄── pyproject.toml               │
│                                                            │
│  Installing dependencies...                                │
│  ████████████████████████████████ 100%                    │
│  ✓ rich                                                   │
│  ✓ click                                                  │
│  ✓ pyyaml                                                 │
│                                                            │
└────────────────────────────────────────────────────────────┘
          │
          ▼
```
*Example: nwave-1.3.0.tar.gz when ${version}=1.3.0*

---

## Step 3: Pre-flight Checks

```
┌─ Step 3: Environment Validation ───────────────────────────┐  Emotion: Confidence
│                                                            │  "Good, it's
│  Resolving install path...                                 │   checking things"
│  └─ NWAVE_INSTALL_PATH not set                            │
│  └─ Using default: ~/.claude/agents/nw/                   │
│                                                            │
│  Validating environment...                                 │
│                                                            │
│  ✓ Python version      3.12.1 (requires 3.10+)            │
│  ✓ pipx isolation      isolated environment active         │
│  ✓ Packages installed  12/12 dependencies verified         │
│  ✓ Install path        ~/.claude/agents/nw/ writable      │
│  ✓ Claude Code         found at /usr/local/bin/claude      │
│                                                            │
│  All checks passed!                                        │
│                                                            │
└────────────────────────────────────────────────────────────┘
          │
          │ ┌─────────────────────────────────────────────┐
          │ │ INTEGRATION CHECKPOINT                      │
          │ │ ✓ ${version} from pyproject.toml = 1.3.0   │
          │ │ ✓ ${install_path} resolved via config      │
          │ └─────────────────────────────────────────────┘
          │
          ▼
```

**Custom Path Example:**
```
┌─ Step 3: Environment Validation (Custom Path) ─────────────┐
│                                                            │
│  Resolving install path...                                 │
│  └─ NWAVE_INSTALL_PATH=~/my-claude/agents/nw/ ◄── env var │
│                                                            │
│  Validating environment...                                 │
│                                                            │
│  ✓ Python version      3.12.1 (requires 3.10+)            │
│  ✓ pipx isolation      isolated environment active         │
│  ✓ Packages installed  12/12 dependencies verified         │
│  ✓ Install path        ~/my-claude/agents/nw/ writable    │
│  ✓ Claude Code         found at /usr/local/bin/claude      │
│                                                            │
│  All checks passed!                                        │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

---

## Step 4: Framework Installation

**Current state (BEFORE - too verbose, walls of logs):**
```
[2026-02-01 00:13:40] INFO: Installing agents...
[2026-02-01 00:13:40] INFO: Installed 47 agent files
[2026-02-01 00:13:40] INFO: Installing commands...
[2026-02-01 00:13:40] INFO: Installed template: step-tdd-cycle-schema.json
[2026-02-01 00:13:40] INFO: Installed template: AGENT_TEMPLATE.yaml
... (16 more template lines) ...
```

**Redesigned TUI (AFTER - modern, visual, delightful):**

```
┌─ Step 4: Installing nWave Framework ───────────────────────┐  Emotion: Anticipation
│                                                            │  "It's building
│  📦 Preparing installation...                              │   my setup!"
│                                                            │
│  ┌────────────────────────────────────────────────────┐   │
│  │  🔄 Checking source files...                       │   │
│  │     ⠹ Comparing timestamps                         │   │
│  └────────────────────────────────────────────────────┘   │
│                                                            │
└────────────────────────────────────────────────────────────┘
          │
          ▼
```

```
┌─ Step 4: Installing nWave Framework ───────────────────────┐  Emotion: Progress
│                                                            │  "Building..."
│  🔨 Building distribution...                               │
│                                                            │
│     ████████████████████░░░░░░░░ 67%                      │
│     Processing agents...                                   │
│                                                            │
└────────────────────────────────────────────────────────────┘
          │
          ▼
```

```
┌─ Step 4: Installing nWave Framework ───────────────────────┐  Emotion: Safety
│                                                            │  "Good, it's
│  🗄️  Creating backup...                                    │   backing up"
│                                                            │
│     ✅ Backup created at ${backup_path}                    │
│        └─ agents, commands, manifest saved                 │
│                                                            │
└────────────────────────────────────────────────────────────┘
          │
          ▼
```

```
┌─ Step 4: Installing nWave Framework ───────────────────────┐  Emotion: Excitement
│                                                            │  "Almost there!"
│  🚀 Installing components to ${install_path}               │
│                                                            │
│     🤖 Agents     ████████████████████ ${agent_count}   ✅ │
│     ⚡ Commands   ████████████████████ ${command_count} ✅ │
│     📋 Templates  ████████████████████ ${template_count}✅ │
│                                                            │
└────────────────────────────────────────────────────────────┘
          │
          ▼
```

```
┌─ Step 4: Validating Installation ──────────────────────────┐  Emotion: Confidence
│                                                            │  "Checking it
│  🔍 Running validation...                                  │   all works"
│                                                            │
│  ┌────────────────────────────────────────────────────┐   │
│  │  Component      Status    Count                    │   │
│  │  ───────────────────────────────────────────────   │   │
│  │  🤖 Agents       ✅        ${agent_count}          │   │
│  │  ⚡ Commands     ✅        ${command_count}        │   │
│  │  📋 Templates    ✅        ${template_count}       │   │
│  │  📜 Manifest     ✅        Created                 │   │
│  │  📐 Schema       ✅        v2.0                    │   │
│  └────────────────────────────────────────────────────┘   │
│                                                            │
│  ✨ Validation: PASSED                                     │
│                                                            │
└────────────────────────────────────────────────────────────┘
          │
          ▼
```
*Example: ${backup_path}=~/.claude/backups/nwave-20260201-001335*

### Design Principles for Step 4:

| Old (Annoying) | New (Delightful) |
|----------------|------------------|
| `[timestamp] INFO: message` | 📦 🚀 🔍 Contextual emoji headers |
| Every file logged individually | Progress bars with counts (30/30 ✅) |
| No visual hierarchy | Nested boxes showing phases |
| Plain text "OK" | ✅ ✓ emoji status indicators |
| 16 template log lines | Single progress bar for templates |
| Verbose timestamps | Clean, implicit progress flow |

### Spinner Animation (for operations < 2s):
```
⠋ ⠙ ⠹ ⠸ ⠼ ⠴ ⠦ ⠧ ⠇ ⠏  (Braille dots)
```

---

## Step 5: Doctor Verification

```
┌─ Step 5: Health Check (Doctor) ────────────────────────────┐  Emotion: Trust
│                                                            │  "It's verifying
│  Running nw doctor...                                      │   everything works"
│                                                            │
│  ┌────────────────────────────────────────────────────┐   │
│  │  nWave Health Check                                │   │
│  ├────────────────────────────────────────────────────┤   │
│  │  ✓ Core installation      ${install_path}         │   │
│  │  ✓ Agent files            ${agent_count} agents   │   │
│  │  ✓ Command files          ${command_count} cmds   │   │
│  │  ✓ Template files         ${template_count} tmpls │   │
│  │  ✓ Config valid           nwave.yaml OK           │   │
│  │  ✓ Permissions            All files accessible    │   │
│  └────────────────────────────────────────────────────┘   │
│                                                            │
│  Status: HEALTHY                                           │
│                                                            │
└────────────────────────────────────────────────────────────┘
          │
          ▼
```
*Example values: ${install_path}=~/.claude/agents/nw/, ${agent_count}=47, ${command_count}=23, ${template_count}=12*

---

## Step 6: Celebration & Welcome

```
┌─ Step 6: Installation Complete ────────────────────────────┐  Emotion: Delighted
│                                                            │  "Wow, that was
│                                                            │   smooth!"
│   ███╗   ██╗██╗    ██╗ █████╗ ██╗   ██╗███████╗           │
│   ████╗  ██║██║    ██║██╔══██╗██║   ██║██╔════╝           │
│   ██╔██╗ ██║██║ █╗ ██║███████║██║   ██║█████╗             │
│   ██║╚██╗██║██║███╗██║██╔══██║╚██╗ ██╔╝██╔══╝             │
│   ██║ ╚████║╚███╔███╔╝██║  ██║ ╚████╔╝ ███████╗           │
│   ╚═╝  ╚═══╝ ╚══╝╚══╝ ╚═╝  ╚═╝  ╚═══╝  ╚══════╝           │
│                                                            │
│   ≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈          │
│                                                            │
│   ✨ nWave v${version} installed successfully!            │
│                                                            │
│   Your Claude is now powered by nWave.                     │
│                                                            │
│   ┌────────────────────────────────────────────────────┐   │
│   │  ⚠️  IMPORTANT: Restart Claude Code to activate    │   │
│   └────────────────────────────────────────────────────┘   │
│                                                            │
│   Next steps:                                              │
│   1. Restart Claude Code (Cmd+Q then reopen)              │
│   2. Try: /nw:version                                     │
│   3. Try: /nw:help                                        │
│                                                            │
│   📚 Docs: ${docs_url}                                    │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

---

## Step 7: User Verifies in Claude

```
┌─ Step 7: Verify in Claude Code ────────────────────────────┐  Emotion: Confident
│                                                            │  "It works!"
│  (User restarts Claude Code, opens terminal)               │
│                                                            │
│  > /nw:version                                            │
│                                                            │
│  nWave Framework v${version} ◄── pyproject.toml           │
│  Installed: ${install_path} ◄── resolved in Step 3        │
│  Agents: ${agent_count} | Commands: ${command_count} | Templates: ${template_count}
│                                                            │
│  ✓ All systems operational                                │
│                                                            │
└────────────────────────────────────────────────────────────┘
          │
          │ ┌─────────────────────────────────────────────┐
          │ │ INTEGRATION CHECKPOINT                      │
          │ │ ✓ ${version} matches Step 6                │
          │ │ ✓ ${install_path} matches Step 3           │
          │ │ ✓ ${agent_count} matches Step 4            │
          │ │ ✓ ${command_count} matches Step 4          │
          │ │ ✓ ${template_count} matches Step 4         │
          │ └─────────────────────────────────────────────┘
          │
          ▼

        ╔═══════════════════════════════════════════════════╗
        ║                                                   ║
        ║   🎉 JOURNEY COMPLETE                            ║
        ║                                                   ║
        ║   User is now ready to use nWave!                ║
        ║                                                   ║
        ╚═══════════════════════════════════════════════════╝
```
*Example: v1.3.0, ~/.claude/agents/nw/, 47 agents, 23 commands, 12 templates*

---

## Shared Artifacts Registry

| Artifact | Source of Truth | Example Value | Displayed In | Risk |
|----------|-----------------|---------------|--------------|------|
| `${version}` | pyproject.toml [project.version] | `1.3.0` | Step 2, 4, 6, 7 | HIGH - must be consistent |
| `${install_path}` | config/installer.yaml + env override | `~/.claude/agents/nw/` | Step 3, 4, 5, 7 | LOW (mitigated) |
| `${backup_path}` | Generated timestamp path | `~/.claude/backups/nwave-20260201-001335` | Step 4 | LOW - unique per install |
| `${agent_count}` | Runtime count dist/ide/agents/ | `47` | Step 4, 5, 7 | LOW - runtime count |
| `${command_count}` | Runtime count dist/ide/commands/ | `23` | Step 4, 5, 7 | LOW - runtime count |
| `${template_count}` | Runtime count dist/ide/templates/ | `12` | Step 4, 5, 7 | LOW - runtime count |
| `${docs_url}` | nWave/data/config/urls.yaml | `https://nwave.dev/getting-started` | Step 6 | MEDIUM - must be reachable |

### Install Path Resolution (Risk Mitigated)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ${install_path} Resolution Order                                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. NWAVE_INSTALL_PATH environment variable    ◄── User override (highest) │
│     │                                                                       │
│     ▼ (if not set)                                                         │
│  2. config/installer.yaml [paths.install_dir]  ◄── Config file             │
│     │                                                                       │
│     ▼ (if not set)                                                         │
│  3. Default: ~/.claude/agents/nw/              ◄── Fallback                │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

Usage Examples:
  # Default installation
  $ pipx install nwave

  # Custom path via environment variable
  $ NWAVE_INSTALL_PATH=~/my-claude/agents/nw pipx install nwave

  # Verify resolved path
  $ nw doctor --show-config
```

---

## Error Paths

### Error 1: pipx Not Installed
- **Detection**: `which pipx` fails
- **Message**: Clear instructions with exact commands
- **Recovery**: User installs pipx, retries
- **Emotion**: Blocked → Informed → Resolved

### Error 2: Python Version Too Old
- **Detection**: `python --version` < 3.10
- **Message**: "Python 3.10+ required. Found: 3.8.10"
- **Recovery**: Suggest pyenv or update instructions
- **Emotion**: Blocked → Frustrated → (needs external action)

### Error 3: Permission Denied
- **Detection**: Cannot write to ~/.claude/
- **Message**: "Cannot write to ~/.claude/. Check permissions."
- **Recovery**: `chmod` suggestion or sudo warning
- **Emotion**: Blocked → Concerned → Resolved

### Error 4: Claude Code Not Found
- **Detection**: `which claude` fails
- **Message**: "Claude Code not found. Install from: code.claude.com"
- **Recovery**: Link to Claude installation
- **Emotion**: Blocked → Informed → (needs external action)

---

## Emotional Arc Summary

```
Excited ─► Anticipation ─► Confidence ─► Excitement ─► Trust ─► Delighted ─► Confident
   │            │              │             │           │          │           │
Step 1      Step 2         Step 3        Step 4      Step 5     Step 6      Step 7
Entry      Download       Pre-flight    Install     Doctor    Celebrate    Verify
```

**Design Principle**: Every step should MAINTAIN or INCREASE confidence. Never let the user wonder "is it working?"

**Key Moments**:
- 📦 Step 4 (Install): Maximum visual feedback with progress bars and spinners
- 🎉 Step 6 (Celebrate): Emotional peak with ASCII logo and success message
- ✅ Step 7 (Verify): Confirmation that closes the loop

---

## Quality Checklist

- [x] Journey complete from trigger to goal
- [x] All steps have explicit CLI output
- [x] Emotional annotations on every step
- [x] Shared artifacts tracked with sources
- [x] Integration checkpoints placed
- [x] Error paths documented with recovery
- [x] Astro/Vite energy achieved (ASCII logo, emoji, celebration)
- [x] Claude restart requirement highlighted
- [x] Version displayed consistently

---

*Journey designed by Luna following question-first methodology. Ready for Eclipse review.*
