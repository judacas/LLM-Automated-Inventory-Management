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

See the checked-in template at [agents/agent.template.toml](../agents/agent.template.toml).
To keep a sample in the repo without auto-loading it, use a filename like `agents/<name>_agent.sample.toml`.

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

These prompts are used by [test_client.py](../test_client.py) to exercise the mounted agent.

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
