# AI Foundry A2A Demo

A demonstration project showcasing the integration of Azure AI Foundry with the Agent-to-Agent (A2A) framework. This project implements an intelligent math agent that uses a portal-managed Azure AI Foundry agent with Code Interpreter to solve problems deterministically by running Python code.

## Features

- **AI Foundry Integration**: Portal-managed agent referenced by name via `azure-ai-projects` SDK
- **Math & Computation**: Solve math problems deterministically with Code Interpreter
- **A2A Framework**: Support agent-to-agent communication and collaboration
- **Conversations API**: Multi-turn conversations via the OpenAI-compatible Responses/Conversations API
- **Streaming**: Real-time streaming responses

## Project Structure

```
├── foundry_agent.py           # AI Foundry math agent (Responses/Conversations API)
├── foundry_agent_executor.py  # A2A framework executor
├── __main__.py                # Main application (starts a2a server)
├── pyproject.toml             # Project dependencies
├── test_client.py             # Test client
└── .env.template              # Environment variables template
```

## Quick Start

### 1. Prerequisites

- Python 3.12+
- An Azure AI Foundry project with a deployed agent (e.g. "Math-Agent") configured
  in the portal with **Code Interpreter** tool enabled
- `az login` completed for DefaultAzureCredential

### 2. Environment Setup

```bash
# Copy environment variables template
cp .env.template .env
```

### 3. Configure Environment Variables

Set the required environment variables in the `.env` file
> NOTE: if you wish to connect another Foundry agent to it you must use port forwarding described below or fully deploy this (future work)


**Agent Card URL Mode**:

The server **always runs locally** on `A2A_HOST:A2A_PORT`. The URL mode controls how the agent advertises itself externally:

- `A2A_URL_MODE=local` – Agent card URL is `http://[host]:[port]/` (for direct local access)
- `A2A_URL_MODE=forwarded` – Agent card URL is set to `A2A_FORWARDED_BASE_URL` (e.g., `https://xyz.devtunnels.ms/`) and can be accessed from there

**Example with Azure DevTunnels**:

```bash
# Create and configure a persistent devtunnel (choose any name for the tunnel as long as its consistent)
devtunnel create [your-tunnel-name-here] -a # note that the -a is to disable auth at forwarding level, we don't have auth set up yet and when we do it would be at a2a level anyways not via devtunnels since this is temporary.
devtunnel port create [your-tunnel-name-here] -p 10007 # you may choose any port as long as you update the A2A_PORT environment variable
devtunnel host [your-tunnel-name-here]
# Note the public URL you receive from this command as you need it later

# Set these environment variables in .env 
A2A_URL_MODE=forwarded
A2A_FORWARDED_BASE_URL=[The URL from the devtunnel host command above]
```

The agent binds to `localhost:10007` locally but advertises itself at the public devtunnel URL in the agent card and then Azure DevTunnels (or whichever port forwarding tool you choose) forwards connections to your local host.

This allows you to use this A2A server as a remote agent in Microsoft Foundry and use the URL as the endpoint.
> NOTE: this is not production ready, Azure DevTunnels is for ad-hoc testing

### 4. Install Dependencies

```bash
# Using uv (recommended)
uv sync
```

### 5. Run the Demo

Open terminal:

```bash
# Start the AI Foundry Math Agent A2A server
uv run .
```

Open another terminal:

```bash
# Run the test client
uv run test_client.py
```

The test client automatically uses the same URL configuration as the server (`A2A_URL_MODE`, `A2A_HOST:A2A_PORT`, or `A2A_FORWARDED_BASE_URL`).

## Agent Capabilities

### Math Skills

1. **Math Computation** (`math_computation`)
   - Solve math problems deterministically using Python code
   - Example: "What is 1247 * 893?"

2. **Math Explanation** (`math_explanation`)
   - Explain mathematical concepts with step-by-step work
   - Example: "Walk me through long division of 1000 by 37"

3. **Data Analysis** (`data_analysis`)
   - Analyse numerical data, compute statistics, generate plots
   - Example: "Compute the first 10 Fibonacci numbers"

### Conversation Example

```
User: What is 1247 * 893?
Agent: 1247 × 893 = 1,113,571

User: Now divide that result by 7.
Agent: 1,113,571 ÷ 7 = 159,081.571428…
```

## Technical Architecture

### Core Components

1. **FoundryMathAgent** (`foundry_agent.py`):
   - References a portal-managed agent by name via `AIProjectClient.agents.get()`
   - Uses the OpenAI-compatible Responses/Conversations API
   - Supports both synchronous and streaming responses

2. **FoundryAgentExecutor** (`foundry_agent_executor.py`):
   - A2A framework executor
   - Streams agent responses back as task updates
   - Maps A2A context IDs to conversation IDs

3. **A2A Integration** (`__main__.py`):
   - Agent card with math-focused skills
   - Starlette server with health check endpoint
