# LLM-Automated-Inventory-Management
This is a group final project for 5 final semester computer engineers at USF working with Microsoft.

## Developer Setup

### Prerequisites
- [uv](https://docs.astral.sh/uv/) (Python 3.11+ will be managed by uv)
- VS Code with the following **required** extensions:
  - **Python** (ms-python.python) - Core Python support with Pylance
  - **Ruff** (charliermarsh.ruff) - Linting and formatting
  
  When you open this workspace, VS Code will prompt you to install these. Click "Install All" to set them up automatically.

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

**Important:** The `uv run pre-commit install` step is required. It sets up Git hooks that automatically run Ruff (formatting and linting) on every commit.

## Code Quality

### Pre-commit Hooks (Local)

Pre-commit hooks run **automatically on every commit** to ensure code is properly formatted and linted before it's committed.

**What runs locally:**
- **Ruff** - Code formatting and linting

If the hooks find issues, the commit will be blocked until you fix them. Most issues can be auto-fixed by Ruff.

**Work-in-progress commits:**
If you need to commit unfinished work (e.g., to save progress or share with teammates), you can bypass the hooks:

```bash
git commit -m "WIP: my unfinished feature" --no-verify
```

⚠️ **Note:** Only use `--no-verify` for temporary WIP commits. All code merged to `main` must pass the checks.

### GitHub Actions (CI)

Additional checks run automatically on GitHub:
- **On push** to any branch except those starting with `dev`
- **On pull requests** to any branch except those starting with `dev`

**What runs on GitHub:**
- **Deptry** - Checks for unused/missing dependencies
- **Gitleaks** - Scans for API keys and secrets

### Why skip `dev` branches?
Branches starting with `dev` (e.g., `dev/my-feature`, `dev-experiment`) skip CI checks to allow rapid iteration during development. Once you're ready to merge, create a PR to a non-dev branch and the checks will run.

### Running Checks Locally

To manually run checks:

```bash
# Run pre-commit hooks manually
uv run pre-commit run --all-files

# Run dependency check
uv run deptry .
```

Or fix formatting automatically:

```bash
uv run ruff format .
uv run ruff check --fix .
```

## Recommended VS Code Extensions

In addition to the required extensions (Python and Ruff), these are recommended but optional:
- **Azure Account** (ms-azuretools.vscode-azure-account) - For Azure authentication
- **GitHub Actions** (github.vscode-github-actions) - For viewing CI status in VS Code
