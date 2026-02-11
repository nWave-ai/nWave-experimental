# nWave Installation Guide

## Prerequisites

Before installing nWave, ensure you have:

- **Python 3.8 or higher** (3.10+ recommended)
- **pipenv** is required for virtual environment and dependency management
- **Git** for version control

### Installing pipenv

If you don't have pipenv installed:

```bash
pip install pipenv
```

Or with pip3:

```bash
pip3 install pipenv
```

## Quick Start

1. Clone the repository and enter the project directory.

2. Install dependencies using pipenv:

```bash
pipenv install --dev
```

3. Run the nWave installer inside the virtual environment:

```bash
pipenv run python scripts/install/install_nwave.py
```

Or activate the shell first:

```bash
pipenv shell
python scripts/install/install_nwave.py
```

## Troubleshooting

### ModuleNotFoundError

If you see a `ModuleNotFoundError`, you are likely running Python outside the virtual environment.

**Solution:** Use pipenv to ensure correct module resolution:

```bash
pipenv run python scripts/install/install_nwave.py
```

### Not in virtual environment

If you get an error about not being in a virtual environment, activate it first:

```bash
pipenv shell
```

Or prefix your commands with `pipenv run`:

```bash
pipenv run python scripts/install/install_nwave.py
```

### Dependency conflicts

If pipenv reports dependency conflicts:

```bash
pipenv install --dev --skip-lock
```
