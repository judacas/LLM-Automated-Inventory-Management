# Contributing to LLM-Automated-Inventory-Management

Thank you for contributing to this project! This guide will help you get started.

## Development Workflow

### 1. Setting Up Your Development Environment

Follow the instructions in [README.md](README.md) to download the code and set up uv
then run

```bash
uv sync
uv run pre-commit install
```

then proceed with development. This installs pre-commit hooks that will automatically run checks before each commit.

For development in VS Code, install the **required** extensions:

- **Python** (ms-python.python) - Core Python support with Pylance
- **Ruff** (charliermarsh.ruff) - Linting and formatting
- **MyPy** (ms-python.mypy-type-checker) - Static type checking

See [Recommended VS Code Extensions](#recommended-vs-code-extensions) below for a complete list of recommended optional extensions that can enhance your development experience.

If you are still using older linters or are having trouble setting up VS Code, the easiest option is to create a new Python profile in VS Code. The profile comes with the basic settings preconfigured for you.

## Recommended VS Code Extensions

In addition to the required extensions, check [.vscode/extensions.json](.vscode/extensions.json) for a complete list of recommended optional extensions that can enhance your development experience.

### 2. Working on a Feature or Fix

1. **Create a branch** from `main`:

   ```bash
   git checkout main
   git pull origin main
   git checkout -b your-name/feature-name
   ```

Note that if you want rapid development without having to run all of the checks, start your branch name with the `dev/` prefix.

1. **Make your changes** following the coding standards below

2. **Test your changes** locally:

   ```bash
   # Run tests
   uv run pytest
   
   # Run linting
   uv run ruff check .
   uv run ruff format .
   
   # Run type checking
   uv run mypy src/
   ```

    For the full list of checks (including pre-commit and dependency checks), see "Running Checks Locally" below.

3. **Commit your changes**:

   ```bash
   git add .
   git commit -m "Brief description of changes"
   ```

   Note: Pre-commit hooks will automatically run. If they fail, fix the issues and commit again.

    **Work-in-progress commits:**
    If you need to commit unfinished work (e.g., to save progress or share with teammates), you can bypass the hooks:

    ```bash
    git commit -m "WIP: my unfinished feature" --no-verify
    ```

    ⚠️ **Note:** Only use `--no-verify` for temporary WIP commits to a branch that starts with dev. All code merged to anywhere else must pass the checks.

4. **Push your branch**:

   ```bash
   git push origin your-name/feature-name
   ```

5. **Create a Pull Request** on GitHub

### 3. Pull Request Guidelines

- **Title**: Use a clear, descriptive title (e.g., "Add inventory update functionality")
- **Description**: Explain what changes you made and why
- **Link Issues**: Reference any related issues
- **Request Reviews**: Tag at least 2 team members for review
- **Address Feedback**: Respond to review comments promptly

### 4. Code Review Process

When reviewing a PR:

- Check that the code follows our standards
- Test the changes locally if possible
- Provide constructive feedback
- Approve only when satisfied with the quality

## Coding Standards

### Python Style

- Follow [PEP 8](https://pep8.org/) style guide
- Use type hints for all function signatures
- Line length is not linted (Ruff ignores `E501`); the formatter still uses 88 as a default target
- Use meaningful variable and function names

### Code Quality Tools

Tooling and exact settings are defined in the configuration files. Treat those as the source of truth and use this section as a quick pointer:

- [pyproject.toml](pyproject.toml) for tool configuration
- [.pre-commit-config.yaml](.pre-commit-config.yaml) for local hook definitions
- [.github/workflows/ci.yml](.github/workflows/ci.yml) for CI checks

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

### Writing Tests

- Place tests in the [tests/](tests/) directory
- Name test files with `test_` prefix (e.g., `test_inventory.py`)
- Test both success and failure cases

Example test structure:

```python
import pytest

def test_example_function():
    """Test that example_function works correctly."""
    result = example_function(input_data)
    assert result == expected_output

def test_example_function_error():
    """Test that example_function raises errors appropriately."""
    with pytest.raises(ValueError):
        example_function(invalid_input)
```

### Documentation

- Add docstrings to all public functions and classes
- Use Google-style docstrings
- Comment complex logic

Example docstring:

```python
def process_order(order_id: int, customer: str) -> dict:
    """Process a customer order.
    
    Args:
        order_id: Unique identifier for the order
        customer: Customer name or email
        
    Returns:
        Dictionary containing order status and details
        
    Raises:
        ValueError: If order_id is invalid
    """
    pass
```

## Git Commit Messages

Write clear commit messages:

- Use present tense ("Add feature" not "Added feature")
- First line: brief summary (50 chars or less)
- Add details in the body if needed
- Reference issues: "Fixes #123" or "Relates to #456"

Good examples:

```text
Add inventory update endpoint

Implement POST /inventory/update endpoint that allows
administrators to update stock quantities.

Fixes #42
```

## Branch Naming Convention

Use descriptive branch names with your name or username:

- `yourname/feature-description` - For new features
- `yourname/fix-description` - For bug fixes
- `yourname/docs-description` - For documentation updates
- `dev/experiment-name` - For experimental work (skips CI)

## Testing Strategy

### Unit Tests

- Test individual functions and classes in isolation
- Use mocks for external dependencies

### Integration Tests

- Test how components work together
- Test API endpoints end-to-end

### Before Pushing

Always run the full test suite:

```bash
uv run pytest -v
```

## Common Issues

### Pre-commit Hooks Failing

If pre-commit hooks fail:

1. Review the error messages
2. Run `uv run ruff format .` to auto-fix formatting
3. Run `uv run ruff check --fix .` to auto-fix linting issues
4. Manually fix any remaining issues
5. Try committing again

### Merge Conflicts

If you have merge conflicts:

1. Pull the latest changes: `git pull origin main`
2. Resolve conflicts in your editor
3. Test that everything still works
4. Commit the merge

## Security

- Never commit secrets, API keys, or credentials
- Use environment variables for sensitive data
- Report security issues privately to the team lead
- Follow the principle of least privilege

## Resources

- [Azure AI Foundry Documentation](https://learn.microsoft.com/azure/ai-studio/)
- [Python Best Practices](https://docs.python-guide.org/)
- [Git Best Practices](https://git-scm.com/book/en/v2)
- [Ruff Documentation](https://docs.astral.sh/ruff/)
- [uv Documentation](https://docs.astral.sh/uv/)
