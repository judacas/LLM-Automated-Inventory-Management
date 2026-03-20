# Troubleshooting

## Startup Fails With Missing Project Endpoint

Symptom:

- startup raises a `ValueError` about `AZURE_AI_PROJECT_ENDPOINT`

Cause:

- the required environment variable is missing or empty

Fix:

- set `AZURE_AI_PROJECT_ENDPOINT` in `.env` or the deployment environment

## Startup Fails Because No Agent Configs Were Found

Symptom:

- startup reports no files matching `*_agent.toml`

Cause:

- `A2A_AGENT_CONFIG_DIR` points to the wrong folder
- the folder exists but contains no matching files

Fix:

- point `A2A_AGENT_CONFIG_DIR` at the correct directory
- verify live agent config file names end with `_agent.toml`
- files ending in `.sample.toml` are ignored on purpose

## Startup Fails Due To Duplicate Slugs

Symptom:

- startup rejects duplicate agent slugs

Cause:

- two files derive to the same slug
- or one file explicitly overrides `a2a.slug` to collide with another

Fix:

- rename one file or give one agent a unique slug

## Startup Fails Due To Duplicate Foundry Agent Names

Symptom:

- startup rejects duplicate Foundry agent names

Cause:

- two mounted A2A agents point at the same `foundry.agent_name`

Fix:

- give each mounted agent its own Foundry agent mapping

## Health Endpoint Works But Real Requests Fail

Symptom:

- `GET /<slug>/health` succeeds
- real A2A requests fail later

Why this happens:

- the health endpoint is local and static
- it does not prove Foundry connectivity

What to check:

- Azure credentials
- Foundry project endpoint
- Foundry agent name
- any network restrictions on the deployed host

## Agent Card Shows Localhost In Azure

Symptom:

- deployed agent cards advertise `http://localhost:...`

Cause:

- the app is still in `A2A_URL_MODE=local`
- or `A2A_FORWARDED_BASE_URL` is unset or wrong

Fix:

- set `A2A_URL_MODE=forwarded`
- set `A2A_FORWARDED_BASE_URL=https://<public-hostname>`
- restart the app

## Dev Tunnel Works In Browser But Not In Client Integrations

Possible causes:

- the forwarded base URL in `.env` does not match the current tunnel host
- the server was started before `.env` was updated
- the tunnel is exposing a different local port

Fix:

- verify the exact printed tunnel URL
- verify the exposed port matches `A2A_PORT`
- restart the A2A server after changing `.env`

## Foundry Agent Not Found

Symptom:

- runtime fails while verifying or calling the configured Foundry agent

Cause:

- `foundry.agent_name` does not exactly match the portal-managed agent name
- the wrong Foundry project endpoint is configured

Fix:

- copy the exact Foundry agent name from the portal
- confirm the project endpoint matches the project where that agent lives

## Requests Lose Context After Restart

Symptom:

- multi-turn behavior resets after the server restarts

Cause:

- conversation tracking is in memory only

Fix:

- expected in the current implementation
- persistent conversation storage would need to be added in code

## App Deploys But Does Not Start Correctly In Azure

Common causes:

- startup command points at the wrong directory
- the deployment artifact omitted `agents/`
- the host is binding to the wrong port or interface
- the team reused the root Dockerfile, which targets `tool_api`, not `a2a_servers`

Fix:

- deploy the correct package
- run from `src/a2a_servers`
- bind to `0.0.0.0`
- include agent config files in the artifact

## Tests Pass But Real Integration Still Fails

Reason:

- unit tests mainly validate configuration and local service behavior
- they do not prove live Foundry connectivity

Next checks:

- run the smoke client against a real configured agent
- verify the deployed public agent card
- inspect Azure host logs for credential or network errors
