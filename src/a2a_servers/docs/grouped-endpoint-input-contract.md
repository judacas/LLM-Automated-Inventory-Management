# Grouped Endpoint Input Contract

## Purpose

A grouped A2A endpoint exposes a single URL that can route to several individual
agent endpoints.  Before forwarding a request, the router parses the intended
target agent from the message text.  This document defines the expected input
format so that the orchestrator prompt can be written correctly.

---

## How to Specify the Target Agent

Include the marker `[target:AGENT_SLUG]` anywhere in the message text.

```
[target:AGENT_SLUG] <rest of message>
```

- `AGENT_SLUG` must match one of the slugs declared in the group's `[group].agents`
  list (see `agents/group.template.toml`).
- The marker is case-insensitive: `[target:Quote]` and `[target:quote]` are
  equivalent.
- The marker can appear at the start, end, or middle of the message.
- Any whitespace between `target:` and the slug is ignored.
- Only the **first** `[target:…]` marker in the message is used.

### Slug naming rules

Slugs are lowercase, alphanumeric, and may contain hyphens (`-`).
They correspond directly to the slug field of each individual `*_agent.toml` file
(derived from the filename or set explicitly via `[a2a].slug`).

Examples of valid slugs: `quote`, `purchase-order`, `email`

---

## Example Inputs

### 1 – Route to the quote agent

```
[target:quote] Check availability for SKU-1001 and prepare a quote for 25 units.
```

### 2 – Route to the purchase-order agent

```
[target:purchase-order] Create a purchase order for 50 units of SKU-2005 from supplier ACME.
```

### 3 – Marker at the end of the message

```
Please send a confirmation email to the customer for order #1042. [target:email]
```

---

## Error Cases

| Situation | Error message |
|---|---|
| No `[target:…]` marker in the message | `No target agent specified. Include [target:AGENT_SLUG] anywhere in your message. Allowed agents: [...]` |
| Marker present but slug not in the group's allowed set | `Unknown target agent 'SLUG'. Allowed agents: [...]` |
| Downstream agent endpoint is unreachable | `Routing error while forwarding to 'SLUG': <HTTP error>` |

All errors are returned as failed A2A task responses so the caller can handle them.

---

## Suggested Orchestrator System Prompt Snippet

Add a clause similar to the following to the orchestrator system prompt so it
knows how to address sub-agents through the grouped endpoint:

```
When routing a request through the grouped A2A endpoint, always include
[target:AGENT_SLUG] somewhere in the message you send, where AGENT_SLUG is
one of the allowed sub-agents for that group endpoint (e.g. quote,
purchase-order, email).  The marker tells the router which individual agent
should handle the request.  Only one target marker per message is supported;
the first one wins.
```

> **Note:** The orchestrator is responsible for choosing the correct target slug.
> The grouped endpoint only validates and routes; it does not attempt to infer
> the intended agent from message content alone.

---

## Adding More Agents to a Group

1. Add the new individual agent's `*_agent.toml` file to the `agents/` directory.
2. Add the new agent's slug to the `[group].agents` list in the relevant
   `*_group.toml` file.
3. Restart the server.

No code changes are required.
