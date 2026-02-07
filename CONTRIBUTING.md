# Contributing to LLM-Automated-Inventory-Management

Thank you for contributing to this project! This guide will help you get started.

## Team Guidelines

This is a team project for 5 computer engineering students. We expect all team members to:

- Communicate regularly (at least weekly meetings)
- Review each other's code
- Follow the established code quality standards
- Document your work clearly
- Ask questions when stuck

## Development Workflow

### 1. Setting Up Your Development Environment

Follow the instructions in [README.md](README.md) to set up your environment with `uv` and pre-commit hooks.

### 2. Working on a Feature or Fix

1. **Create a branch** from `main`:
   ```bash
   git checkout main
   git pull origin main
   git checkout -b your-name/feature-name
   ```

2. **Make your changes** following the coding standards below

3. **Test your changes** locally:
   ```bash
   # Run tests
   uv run pytest
   
   # Run linting
   uv run ruff check .
   uv run ruff format .
   
   # Run type checking
   uv run mypy src/
   ```

4. **Commit your changes**:
   ```bash
   git add .
   git commit -m "Brief description of changes"
   ```
   
   Note: Pre-commit hooks will automatically run. If they fail, fix the issues and commit again.

5. **Push your branch**:
   ```bash
   git push origin your-name/feature-name
   ```

6. **Create a Pull Request** on GitHub

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
- Maximum line length: 88 characters (enforced by Ruff)
- Use meaningful variable and function names

### Code Quality Tools

We use the following tools (configured in `pyproject.toml`):

- **Ruff**: Linting and formatting
- **MyPy**: Static type checking
- **Pytest**: Testing framework
- **Coverage**: Code coverage reporting
- **Deptry**: Dependency checking

### Writing Tests

- Place tests in the `tests/` directory
- Name test files with `test_` prefix (e.g., `test_inventory.py`)
- Aim for high test coverage (>80%)
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
- Update README.md if you add new features
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
```
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
uv run pytest -v --cov
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

### Need Help?

- Ask in team meetings
- Post in the team chat
- Tag team members in GitHub issues/PRs
- Refer to project documentation

## Code of Conduct

- Be respectful and professional
- Welcome diverse perspectives
- Focus on constructive feedback
- Help each other learn and grow
- Keep communication timely

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
