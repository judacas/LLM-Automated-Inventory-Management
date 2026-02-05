---
name: run-linting
description: Runs linting and LSP diagnostics to list all errors and warnings in the workspace. Use when fixing linter errors, checking code quality, or when the linter-fixer subagent or user asks to see all lint/LSP issues.
---

# Run Linting and See All Errors

Use this workflow to get a complete list of linter and LSP diagnostics before fixing them.

**ReadLints** is a tool the agent has: it returns the current workspace’s LSP/linter diagnostics (what the editor shows — e.g. Ruff, Pyright). **Ruff CLI** (`uv run ruff check --fix`) is a separate run over the whole project. They often report the same issues when Ruff is the main linter, but aren’t identical: the IDE may be stale or include other sources; Ruff CLI is the canonical full-project pass. Use both for full coverage.

## 1. Run Ruff on the entire project (required)

Always run:

```bash
uv run ruff check --fix
```

This runs Ruff over the whole project. Capture the output and treat it as the authoritative list of Ruff issues.

## 2. Read LSP/linter diagnostics (optional extra)

Use the **ReadLints** tool to get IDE diagnostics — same or overlapping with Ruff in many setups, but can include other LSP sources (e.g. Pyright) or reflect unsaved state.

- **Paths**: Pass the path(s) you care about, or omit for the whole workspace.
- Interpret each diagnostic: file, line, severity, message, and optional source.

Combine with the Ruff output: merge by file/line, dedupe when they refer to the same issue.

## 3. Consolidate and prioritize

- Treat **errors** as must-fix; **warnings** as should-fix when feasible.
- Group by file so fixes can be applied in one pass per file.
- Note any diagnostics that need broader context so they can be delegated instead of auto-fixed.

## Summary

1. **Always** run `uv run ruff check --fix` on the entire project.
2. Optionally call **ReadLints** for IDE diagnostics and merge with Ruff output.
3. List all issues by file and severity; flag any that need human or main-agent context.
