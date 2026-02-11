# nWave Framework Installation Guide

This guide helps you install the nWave ATDD framework to your global Claude config directory, making 13 specialized agents (+ 13 reviewer agents) available across all your projects.

## Prerequisites

Before installing nWave, ensure you have:

- **Python 3.8 or higher** (tested on Python 3.8, 3.9, 3.10, 3.11, 3.12)
- **pipenv** (required for virtual environment and dependency management)

### Installing pipenv

If pipenv is not installed, install it first:

```bash
# Install pipenv globally
pip install pipenv
# Or using pip3
pip3 install pipenv
```

## Quick Start

### All Platforms (Using pipenv - Recommended)

```bash
# Clone the repository
git clone https://github.com/nWave-ai/nWave.git
cd crafter-ai

# Install dependencies in virtual environment
pipenv install --dev

# Run the installer
pipenv run python scripts/install/install_nwave.py

# Or activate the shell and run directly
pipenv shell
python scripts/install/install_nwave.py
```

### Standalone Installer (Alternative)

```bash
# Download the standalone installer
curl -O https://github.com/nWave-ai/nWave/releases/latest/download/install-nwave-claude-code.py

# Run within pipenv environment
pipenv run python install-nwave-claude-code.py
```

**Prerequisites**: Python 3.8 or higher, pipenv required

## What Gets Installed

### Framework Components

- **26 Specialized AI Agents** (13 primary + 13 reviewers) organized by wave and role
- **cai/atdd Command Interface** with intelligent project analysis
- **Wave Processing Architecture** with clean context isolation
- **Centralized Configuration System** (constants.md)
- **Quality Validation Network** with Level 1-6 refactoring
- **Second Way DevOps**: Observability agents (metrics, logs, traces, performance)
- **Third Way DevOps**: Experimentation agents (A/B testing, hypothesis validation, learning synthesis)

### Agent Categories

- 🟦 **Requirements Analysis** (5 agents) - Business requirements, UX, Security, Legal
- 🟧 **Architecture Design** (3 agents) - System design, technology selection
- ❤️ **Test Design** (1 agent) - Acceptance test creation
- 🟢 **Development** (1 agent) - Outside-in TDD implementation
- ❤️ **Quality Validation** (8 agents) - Comprehensive quality assurance
- 🔵 **Refactoring** (2 agents) - Systematic code improvement
- ⚫ **Coordination** (11 agents) - Workflow orchestration
- 📊 **Observability** (4 agents) - Second Way DevOps monitoring and feedback
- 🧪 **Experimentation** (4 agents) - Third Way DevOps learning and optimization

### Installation Location

```
~/.claude/                           # Global Claude config directory
├── agents/
│   └── cai/                        # nWave agent specifications
│       ├── constants.md            # Centralized configuration
│       ├── requirements-analysis/  # Blue family agents (5)
│       ├── architecture-design/    # Orange family agents (3)
│       ├── test-design/           # Test design agents (1)
│       ├── development/           # Development agents (1)
│       ├── quality-validation/    # Quality validation agents (8)
│       ├── refactoring/           # Refactoring agents (2)
│       ├── coordination/          # Coordination agents (11)
│       ├── observability/         # Second Way DevOps agents (4)
│       ├── experimentation/       # Third Way DevOps agents (4)
│       └── legacy-agents/         # Deprecated agents
└── commands/                       # Command integrations
    └── cai/
        ├── atdd.md               # Main ATDD workflow command
        └── root-why.md           # Root cause analysis command
```

## Installation Options

### Standard Installation

Installs the complete framework with automatic backup:

```bash
./install-nwave.sh                    # macOS/Linux
.\install-nwave.ps1                   # Windows PowerShell
install-nwave.bat                     # Windows Command Prompt
```

### Backup Only

Creates backup without installing (useful before upgrades):

```bash
./install-nwave.sh --backup-only      # macOS/Linux
.\install-nwave.ps1 -BackupOnly       # Windows PowerShell
install-nwave.bat --backup-only       # Windows Command Prompt
```

### Restore Previous Installation

Restores from the most recent backup:

```bash
./install-nwave.sh --restore          # macOS/Linux
.\install-nwave.ps1 -Restore          # Windows PowerShell
install-nwave.bat --restore           # Windows Command Prompt
```

### Help

Shows detailed usage information:

```bash
./install-nwave.sh --help             # macOS/Linux
.\install-nwave.ps1 -Help             # Windows PowerShell
install-nwave.bat --help              # Windows Command Prompt
```

## What Gets Excluded

The installation script **excludes** project-specific files:

- `README.md` (main project documentation)
- `.claude/agents/cai/README.md` (agent overview documentation)
- `docs/craft-ai/` directory (project working files)
- Git configuration and project metadata

This ensures a clean separation between the reusable framework and project-specific documentation.

## Installation Features

### Automatic Backup

- Creates timestamped backup of existing installation
- Preserves customizations and previous versions
- Enables easy rollback if needed

### Validation

- Verifies all framework files are copied correctly
- Checks agent category structure
- Validates core components (constants.md, cai/atdd command)
- Generates installation manifest

### Cross-Platform Compatibility

- **Bash script** for macOS/Linux systems
- **PowerShell script** for modern Windows systems
- **Batch script** for legacy Windows systems
- Consistent behavior across all platforms

### Error Handling

- Comprehensive error checking and reporting
- Graceful failure with helpful messages
- Automatic cleanup on errors
- Rollback capability

## Usage After Installation

### Command Interface

Use the `cai/atdd` command in any project:

```bash
# Basic workflow initiation with project analysis
cai/atdd "implement user authentication system"

# Explicit project analysis
cai/atdd "add payment processing" --analyze-existing

# Start from specific ATDD stage
cai/atdd "OAuth2 integration" --from-stage=architect

# Resume existing workflow
cai/atdd --resume auth-feature-2024-01

# Check workflow status
cai/atdd --status

# Get help
cai/atdd --help
```

### Global Agent Access

All 26 agents (13 primary + 13 reviewers) are available globally:

- Access specialized expertise (UX, Security, Legal, DevOps) when needed
- Use centralized configuration across all projects
- Benefit from wave processing architecture
- Apply systematic quality validation
- Leverage Second Way observability and monitoring
- Enable Third Way experimentation and continuous learning

## Troubleshooting

### ModuleNotFoundError

If you see `ModuleNotFoundError: No module named 'xxx'`:

```bash
# Ensure you're running within pipenv virtual environment
pipenv install --dev
pipenv run python scripts/install/install_nwave.py

# Or check if dependencies are installed
pipenv run pip list

# If packages are missing, reinstall
pipenv install --dev
```

### Not in Virtual Environment

If you see errors about not being in a virtual environment:

```bash
# Always use pipenv to manage your environment
pipenv install --dev

# Run commands using pipenv run
pipenv run python scripts/install/install_nwave.py

# Or activate the shell
pipenv shell
python scripts/install/install_nwave.py
```

### Pipenv Issues

If pipenv commands fail:

```bash
# Ensure pipenv is installed
pip install pipenv

# Clear and recreate the virtual environment
pipenv --rm
pipenv install --dev

# Verify pipenv is working
pipenv --version
```

### Permission Issues

If you encounter permission errors:

```bash
# macOS/Linux: Make script executable
chmod +x install-nwave.sh

# Windows: Run as Administrator if needed
# Right-click → "Run as administrator"
```

### Path Issues

If the script can't find the framework source:

```bash
# Ensure you're running from the nwave project directory
cd /path/to/nwave

# Use pipenv to run the installer
pipenv run python scripts/install/install_nwave.py
```

### Existing Installation

If you have an existing installation:

- The script automatically creates a backup
- You can restore with `--restore` option
- Check `~/.claude/backups/` for backup files

### Validation Failures

If installation validation fails:

- Check the installation log: `~/.claude/nwave-install.log`
- Verify source framework is complete
- Ensure you ran within pipenv environment: `pipenv run ...`
- Use `--restore` to rollback
- Report issues with log details

## Uninstallation

To remove the nWave framework:

```bash
# Remove framework directories
rm -rf ~/.claude/agents/
rm -rf ~/.claude/commands/cai/

# Or restore from a pre-installation backup
./install-nwave.sh --restore
```

## Updates

To update to a newer version:

1. Download the latest nWave framework
2. Run the installation script (creates automatic backup)
3. The new version overwrites the old installation
4. Use `--restore` if you need to rollback

## Support

- **Documentation**: Complete framework documentation in this repository
- **Issues**: Report problems on GitHub
- **Help**: Use `cai/atdd --help` for command help
- **Logs**: Check `~/.claude/nwave-install.log` for installation details

---

**Next Steps**: After installation, navigate to any project and use `cai/atdd "your feature description"` to start your first ATDD workflow with intelligent project analysis!
