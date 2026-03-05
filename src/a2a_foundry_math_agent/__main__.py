import logging
import os

import click
import uvicorn
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from dotenv import load_dotenv
from foundry_agent_executor import create_foundry_agent_executor
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route

load_dotenv()

logger = logging.getLogger(__name__)


@click.command()
@click.option("--host", "host", default=None)
@click.option("--port", "port", type=int, default=None)
@click.option(
    "--url-mode",
    "url_mode",
    type=click.Choice(["local", "forwarded"], case_sensitive=False),
    default=None,
)
@click.option("--forwarded-base-url", "forwarded_base_url", default=None)
def main(
    host: str | None,
    port: int | None,
    url_mode: str | None,
    forwarded_base_url: str | None,
) -> None:
    """Start the AI Foundry Math Agent a2a server."""
    resolved_host: str = (
        host if host is not None else os.getenv("A2A_HOST", "localhost")
    )
    resolved_port: int = (
        port if port is not None else int(os.getenv("A2A_PORT", "10007"))
    )

    log_level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_name, logging.INFO)
    logging.basicConfig(level=log_level)

    selected_url_mode = (
        (url_mode or os.getenv("A2A_URL_MODE") or "local").strip().lower()
    )
    selected_forwarded_base_url = (
        forwarded_base_url or os.getenv("A2A_FORWARDED_BASE_URL") or ""
    ).strip()

    if selected_url_mode not in {"local", "forwarded"}:
        raise ValueError("A2A_URL_MODE must be either 'local' or 'forwarded'")

    # Build the agent card URL based on the mode.
    # NOTE: The server always binds to resolved_host:resolved_port (locally).
    # The agent card URL is just metadata for discovery; it tells external clients
    # how to reach the server. Use "local" for direct access, or "forwarded" when
    # using reverse proxies (e.g., Azure DevTunnels, ngrok).
    if selected_url_mode == "forwarded":
        if not selected_forwarded_base_url:
            raise ValueError(
                "A2A_FORWARDED_BASE_URL is required when A2A_URL_MODE=forwarded"
            )
        agent_card_base_url = selected_forwarded_base_url.rstrip("/")
    else:
        agent_card_base_url = f"http://{resolved_host}:{resolved_port}"

    agent_card_url = f"{agent_card_base_url}/"
    # Verify required environment variables
    required_env_vars = [
        "AZURE_AI_PROJECT_ENDPOINT",
        "AZURE_AI_AGENT_NAME",
    ]

    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    if missing_vars:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing_vars)}"
        )

    # Define agent skills
    skills = [
        AgentSkill(
            id="math_computation",
            name="Math Computation",
            description="Solve math problems deterministically using Code Interpreter to run Python code",
            tags=["math", "computation", "code-interpreter"],
            examples=[
                "What is 1247 * 893?",
                "Calculate the derivative of x^3 + 2x",
                "What is the integral of sin(x) from 0 to pi?",
            ],
        ),
        AgentSkill(
            id="math_explanation",
            name="Math Explanation",
            description="Explain mathematical concepts and show step-by-step work",
            tags=["math", "education", "explanation"],
            examples=[
                "Explain how to solve quadratic equations",
                "Walk me through long division of 1000 by 37",
                "Why does 0! equal 1?",
            ],
        ),
        AgentSkill(
            id="data_analysis",
            name="Data Analysis",
            description="Analyse numerical data, compute statistics, and generate plots",
            tags=["math", "statistics", "data"],
            examples=[
                "What's the standard deviation of [4, 8, 15, 16, 23, 42]?",
                "Plot y = x^2 from -10 to 10",
                "Compute the first 10 Fibonacci numbers",
            ],
        ),
    ]

    # Create agent card
    agent_card = AgentCard(
        name="AI Foundry Math Agent",
        description="An intelligent math agent powered by Azure AI Foundry with Code Interpreter. "
        "I solve math problems deterministically by running Python code, explain concepts, "
        "and analyse numerical data.",
        url=agent_card_url,
        version="2.0.0",
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=AgentCapabilities(streaming=True),
        skills=skills,
    )

    # Create agent executor
    agent_executor = create_foundry_agent_executor(agent_card)

    # Create request handler
    request_handler = DefaultRequestHandler(
        agent_executor=agent_executor, task_store=InMemoryTaskStore()
    )

    # Create A2A application
    a2a_app = A2AStarletteApplication(
        agent_card=agent_card, http_handler=request_handler
    )

    # Get routes
    routes = a2a_app.routes()

    # Add health check endpoint
    async def health_check(request: Request) -> PlainTextResponse:
        return PlainTextResponse("AI Foundry Math Agent is running!")

    routes.append(Route(path="/health", methods=["GET"], endpoint=health_check))

    # Create Starlette app
    app = Starlette(routes=routes)

    # Log startup information
    logger.info(f"Starting AI Foundry Math Agent on {resolved_host}:{resolved_port}")
    logger.info(f"Agent card URL mode: {selected_url_mode}")
    if selected_url_mode == "forwarded":
        logger.info(f"Agent is behind reverse proxy. External URL: {agent_card_url}")
    else:
        logger.info(f"Agent card URL (local): {agent_card_url}")
    logger.info(f"Agent card: {agent_card.name}")
    logger.info(f"Skills: {[skill.name for skill in skills]}")
    logger.info(
        f"Health check available at: http://{resolved_host}:{resolved_port}/health"
    )

    # Run the server
    uvicorn.run(app, host=resolved_host, port=resolved_port)


if __name__ == "__main__":
    main()
