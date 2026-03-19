# Agent Definition Reference

## Overview

Each mounted A2A agent is defined by a TOML file matching:

```text
agents/*_agent.toml
```

These files are discovered automatically at startup.

## Required Sections

Each agent file must contain:

- `[a2a]`
- `[foundry]`
- at least one `[[skills]]`

Optional:

- `[smoke_tests]`

## Example Skeleton

See the checked-in template at [agents/agent.template.toml](/home/judacas/Documents/code/LLM-Automated-Inventory-Management/src/a2a_servers/agents/agent.template.toml).

## `[a2a]` Section

Required keys:

- `name`
- `description`
- `version`
- `health_message`

Optional keys:

- `slug`
- `default_input_modes`
- `default_output_modes`
- `streaming`

Behavior notes:

- if `slug` is omitted, it is derived from the filename
- slugs are normalized to lowercase URL-safe segments
- `streaming` defaults to `true`
- input and output modes default to `["text"]`

## `[foundry]` Section

Required key:

- `agent_name`

This must exactly match the portal-managed Azure AI Foundry agent name the server should call.

## `[[skills]]` Blocks

At least one skill block is required.

Each skill must include:

- `id`
- `name`
- `description`

Optional arrays:

- `tags`
- `examples`

These values are published in the A2A agent card, so they should be written for discoverability by other humans and agents.

## `[smoke_tests]` Section

Optional key:

- `prompts`

If present, `prompts` must be a list of non-empty strings.

These prompts are used by [test_client.py](/home/judacas/Documents/code/LLM-Automated-Inventory-Management/src/a2a_servers/test_client.py) to exercise the mounted agent.

If omitted, the client falls back to a generic prompt.

## Slug Rules

Slug resolution follows this order:

1. use `[a2a].slug` if provided
2. otherwise derive from the filename

Filename examples:

- `math_agent.toml` -> `math`
- `quote_agent.toml` -> `quote`
- `assistant-agent.toml` -> `assistant`

Normalization behavior:

- lowercase only
- non-alphanumeric separators become `-`
- repeated separators collapse

## Startup Validation

Startup fails if:

- the config directory does not exist
- no `*_agent.toml` files are found
- a required section is missing
- a required field is missing or empty
- `streaming` is not a boolean
- `slug` is invalid
- there are duplicate slugs
- there are duplicate Foundry agent names

## Conventions For New Agents

Use these conventions so the published A2A metadata stays useful:

- `name`: client-facing and specific
- `description`: explain when another agent should call this agent
- `skills`: reflect capabilities, not implementation details
- `examples`: use realistic prompts from the Contoso scenario
- `smoke_tests.prompts`: include happy-path prompts that prove the main capability

## Example Review Checklist

Before merging a new agent definition, check:

- the filename ends with `_agent.toml`
- the slug is stable and intentional
- the Foundry agent name exists
- skills metadata reads clearly to another team
- smoke tests represent the real use case
- the agent appears correctly in `GET /`

---

## Grouped Endpoint Definitions

Grouped endpoints are defined in files matching:

```text
agents/*_group.toml
```

They act as A2A routers that forward requests to individual agent endpoints.
Groups are **optional**; the server starts normally if no `*_group.toml` files exist.

### Required sections

- `[a2a]` — same required keys as individual agents (`name`, `description`, `version`, `health_message`)
- `[group]` — with a required `agents` key listing the slugs of allowed member agents
- at least one `[[skills]]` entry

### `[group]` Section

Required key:

- `agents` — a non-empty list of agent slugs (strings).  Each slug must match
  the slug of an existing `*_agent.toml` definition; the server will reject an
  unknown slug at startup.

Example:

```toml
[group]
agents = ["quote", "purchase-order", "email"]
```

### Slug derivation

Group slugs follow the same rules as agent slugs, but the `_group` / `-group`
suffix is stripped instead of `_agent` / `-agent`.

Examples:

- `inventory_group.toml` → `inventory`
- `ops-group.toml` → `ops`

### Startup validation

Startup fails if:

- a group member slug does not match any loaded individual agent slug
- a group slug collides with an individual agent slug
- there are duplicate group slugs

### Input format for grouped endpoints

See [grouped-endpoint-input-contract.md](grouped-endpoint-input-contract.md).

### Template

See `agents/group.template.toml` for a ready-to-copy skeleton.
