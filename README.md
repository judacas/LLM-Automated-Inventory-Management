# LLM-Automated-Inventory-Management

[![CI](https://github.com/judacas/LLM-Automated-Inventory-Management/actions/workflows/ci.yml/badge.svg)](https://github.com/judacas/LLM-Automated-Inventory-Management/actions/workflows/ci.yml)

This is a group final project for 5 final semester computer engineers at USF working with Microsoft.

## Developer Setup

### Prerequisites

- [uv](https://docs.astral.sh/uv/) (Python 3.11+ will be managed by uv)
- VS Code with the following **required** extensions:
  - **Python** (ms-python.python) - Core Python support with Pylance
  - **Ruff** (charliermarsh.ruff) - Linting and formatting
  - **MyPy** (ms-python.mypy-type-checker) - Static type checking
  
  When you open this workspace, VS Code will prompt you to install these. Click "Install All" to set them up automatically. (note that this will also install optional tools like azure mcp etc which imo help speed up development)

### Initial Setup

```bash
# Clone the repo
git clone <repo-url>
cd LLM-Automated-Inventory-Management

# Install all dependencies (including dev dependencies)
uv sync

# Install pre-commit hooks (required for formatting/linting on commits)
uv run pre-commit install
```

**Important:** The `uv run pre-commit install` step is required. It sets up Git hooks that automatically run Ruff (formatting and linting) on every commit. This repo enforces code quality so by running the precommit you assure yourself that your commmits will pass the CI tests

## Code Quality

All tooling configuration lives in the repo config files. This section describes how to run checks, but treat these files as the source of truth:

- [pyproject.toml](pyproject.toml)
- [.pre-commit-config.yaml](.pre-commit-config.yaml)
- [.github/workflows/ci.yml](.github/workflows/ci.yml)

### Pre-commit Hooks (Local)

Pre-commit hooks run **automatically on every commit** to ensure code is properly formatted and linted before it's committed.

**What runs locally:**

- **Ruff** - Code formatting and linting
- **MyPy** - Static type checking

If the hooks find issues, the commit will be blocked until you fix them. Most issues can be auto-fixed by Ruff.

**Work-in-progress commits:**
If you need to commit unfinished work (e.g., to save progress or share with teammates), you can bypass the hooks:

```bash
git commit -m "WIP: my unfinished feature" --no-verify
```

⚠️ **Note:** Only use `--no-verify` for temporary WIP commits to a branch that starts with dev. All code merged to anywhere else must pass the checks.

### GitHub Actions (CI)

Additional checks run automatically on GitHub:

- **On push** to any branch except those starting with `dev`
- **On pull requests** to any branch except those starting with `dev`

**What runs on GitHub:**

- **Ruff** - Code formatting and linting
- **MyPy** - Static type checking
- **Pytest** - Unit tests
- **Deptry** - Checks for unused/missing dependencies
- **Gitleaks** - Scans for API keys and secrets
- **GitHub Copilot** - Automated code review and suggestions

### Why skip `dev` branches?

Branches starting with `dev` (e.g., `dev/my-feature`, `dev-experiment`) skip CI checks to allow rapid iteration during development. Once you're ready to merge, create a PR to a non-dev branch and the checks will run.

### Running Checks Locally

To manually run checks:

```bash
# Run pre-commit hooks manually
uv run pre-commit run --all-files

# Run tests
uv run pytest

# Run dependency check
uv run deptry .

# Run type checking
uv run mypy src/
```

Or fix formatting automatically:

```bash
uv run ruff format .
uv run ruff check --fix .
```

## Recommended VS Code Extensions

## Recommended VS Code Extensions

In addition to the required extensions, check [.vscode/extensions.json](.vscode/extensions.json) for a complete list of recommended optional extensions that can enhance your development experience.


## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our development workflow, coding standards, and how to submit pull requests.

