import argparse
import logging  # Import the logging module
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
from a2a.client import A2ACardResolver, A2AClient
from a2a.types import (
    AgentCard,
    MessageSendParams,
    SendMessageRequest,
)
from a2a.utils.constants import (
    AGENT_CARD_WELL_KNOWN_PATH,
    EXTENDED_AGENT_CARD_PATH,
)
from agent_definition import AgentDefinition, load_agent_definitions
from dotenv import load_dotenv
from settings import ServerSettings, load_server_settings


async def check_agent_health(
    base_url: str, httpx_client: httpx.AsyncClient, logger: logging.Logger
) -> bool:
    """Test if the agent server is healthy and responsive."""
    try:
        health_url = f"{base_url}/health"
        logger.info(f"🏥 Checking agent health at: {health_url}")

        response = await httpx_client.get(health_url)
        if response.status_code == 200:
            logger.info("✅ Agent server is healthy and responsive")
            return True
        logger.warning(f"⚠️  Agent health check returned status: {response.status_code}")
        return False

    except Exception as e:
        logger.error(f"❌ Agent health check failed: {e}")
        return False


def extract_text_from_parts(parts: list[Any]) -> str:
    """Extract all text content from a list of message parts."""
    texts = []
    for part in parts:
        # Unwrap Part RootModel wrapper if present (a2a Parts are Pydantic
        # RootModel instances whose inner value lives on .root)
        inner = part.root if hasattr(part, "root") else part
        if isinstance(inner, dict):
            if inner.get("kind") == "text":
                texts.append(inner.get("text", ""))
        elif hasattr(inner, "kind") and inner.kind == "text":
            texts.append(inner.text)
    return "\n".join(texts)


def extract_text_from_message(message: Any) -> str:
    """Extract text from a Message object or dict."""
    if isinstance(message, dict):
        return extract_text_from_parts(message.get("parts", []))
    elif hasattr(message, "parts"):
        return extract_text_from_parts(message.parts)
    return ""


async def print_detailed_response(
    response: Any, logger: logging.Logger, response_type: str = "Response"
) -> None:
    """Print detailed response information in a readable format."""
    try:
        # The response is a SendMessageResponse with .root
        result_obj = response
        if hasattr(response, "root"):
            result_obj = response.root

        # Check for error
        if hasattr(result_obj, "error") and result_obj.error is not None:
            logger.error(f"❌ {response_type} Error: {result_obj.error}")
            return

        # Get the result (Task or Message)
        result = getattr(result_obj, "result", result_obj)

        logger.info(f"📋 {response_type}:")

        # If it's a Message (has role and parts)
        if hasattr(result, "kind") and result.kind == "message":
            text = extract_text_from_message(result)
            if text:
                logger.info(f"🤖 Agent: {text}")
            return

        # If it's a Task (has status, artifacts, history)
        if hasattr(result, "status"):
            status = result.status
            logger.info(f"   State: {status.state}")
            if status.message:
                text = extract_text_from_message(status.message)
                if text:
                    logger.info(f"🤖 Agent response:\n{text}")

        if hasattr(result, "artifacts") and result.artifacts:
            for artifact in result.artifacts:
                text = extract_text_from_parts(artifact.parts)
                if text:
                    logger.info(f"📎 Artifact:\n{text}")

    except Exception as e:
        logger.debug(f"Could not parse response details: {e}")


async def smoke_test_agent(
    definition: AgentDefinition,
    settings: ServerSettings,
    logger: logging.Logger,
    *,
    public_base_url_override: str | None = None,
) -> dict[str, Any]:
    if public_base_url_override:
        base_url = (
            f"{public_base_url_override.rstrip('/')}/{definition.slug.strip('/')}"
        )
    else:
        base_url = settings.agent_base_url_for(definition.slug)

    logger.info("Connecting to A2A agent at: %s", base_url)
    logger.info("Loaded smoke-test config from: %s", definition.source_path)

    async with httpx.AsyncClient(timeout=120) as httpx_client:
        if not await check_agent_health(base_url, httpx_client, logger):
            logger.error(
                "❌ Agent server appears to be unhealthy. Please check the server."
            )
            return {
                "slug": definition.slug,
                "agent_name": definition.public_name,
                "base_url": base_url,
                "prompt_count": 0,
                "success_count": 0,
                "failure_count": 1,
                "health_ok": False,
            }

        resolver = A2ACardResolver(
            httpx_client=httpx_client,
            base_url=base_url,
        )

        final_agent_card_to_use: AgentCard | None = None

        try:
            logger.info(
                f"🔍 Attempting to fetch public agent card from: {base_url}{AGENT_CARD_WELL_KNOWN_PATH}"
            )
            _public_card = await resolver.get_agent_card()
            logger.info("✅ Successfully fetched public agent card:")
            logger.info(f"   Agent Name: {_public_card.name}")
            logger.info(f"   Description: {_public_card.description}")
            logger.info(f"   Skills: {len(_public_card.skills)} available")
            for skill in _public_card.skills:
                logger.info(f"     - {skill.name}: {skill.description}")

            final_agent_card_to_use = _public_card
            logger.info(
                "\n📋 Using PUBLIC agent card for client initialization (default)."
            )

            if _public_card.supports_authenticated_extended_card:
                try:
                    logger.info(
                        f"\n🔒 Public card supports authenticated extended card. Attempting to fetch from: {base_url}{EXTENDED_AGENT_CARD_PATH}"
                    )
                    auth_headers_dict = {
                        "Authorization": "Bearer demo-token-for-foundry-agent"
                    }
                    _extended_card = await resolver.get_agent_card(
                        relative_card_path=EXTENDED_AGENT_CARD_PATH,
                        http_kwargs={"headers": auth_headers_dict},
                    )
                    logger.info(
                        "✅ Successfully fetched authenticated extended agent card:"
                    )
                    logger.info(f"   Extended Agent Name: {_extended_card.name}")
                    logger.info(
                        f"   Additional Capabilities: {_extended_card.capabilities}"
                    )
                    final_agent_card_to_use = _extended_card
                    logger.info(
                        "\n🔐 Using AUTHENTICATED EXTENDED agent card for client initialization."
                    )
                except Exception as e_extended:
                    logger.warning(
                        f"⚠️  Failed to fetch extended agent card: {e_extended}. Will proceed with public card."
                    )
            elif _public_card:
                logger.info(
                    "\n📖 Public card does not indicate support for an extended card. Using public card."
                )

        except Exception as e:
            logger.error(f"❌ Critical error fetching public agent card: {e}")
            logger.info("💡 Make sure the A2A server is running:")
            logger.info("   uv run python __main__.py")
            raise RuntimeError(
                "Failed to fetch the public agent card. Cannot continue."
            ) from e

        client = A2AClient(
            httpx_client=httpx_client,
            agent_card=final_agent_card_to_use,
        )
        logger.info(
            "✅ A2AClient initialized using agent card URL: %s",
            final_agent_card_to_use.url,
        )

        smoke_test_messages = list(definition.smoke_test_prompts)
        if not smoke_test_messages:
            smoke_test_messages = [
                "Tell me what you can help with and give one example request."
            ]

        logger.info(
            "\n🧪 Testing %s smoke-test prompts for %s:",
            len(smoke_test_messages),
            definition.public_name,
        )
        success_count = 0
        failure_count = 0

        for i, test_message in enumerate(smoke_test_messages, 1):
            logger.info(f"\n--- Test {i}/{len(smoke_test_messages)} ---")
            logger.info(f"💬 User: {test_message}")

            send_message_payload: dict[str, Any] = {
                "message": {
                    "role": "user",
                    "parts": [{"kind": "text", "text": test_message}],
                    "messageId": uuid4().hex,
                },
            }

            try:
                request = SendMessageRequest(
                    id=str(uuid4()),
                    params=MessageSendParams(**send_message_payload),
                )

                logger.info("📤 Sending message...")
                response = await client.send_message(request)
                await print_detailed_response(
                    response, logger, "Regular Message Response"
                )
                result_obj = response.root if hasattr(response, "root") else response
                if hasattr(result_obj, "error") and result_obj.error is not None:
                    failure_count += 1
                else:
                    success_count += 1

            except Exception as e:
                logger.error(f"❌ Error testing message '{test_message[:30]}...': {e}")
                failure_count += 1

        logger.info("\n🎉 Agent smoke testing completed!")
        logger.info("📊 Agent Summary:")
        logger.info(f"   - Agent: {final_agent_card_to_use.name}")
        logger.info(f"   - Base URL: {base_url}")
        logger.info(f"   - Test Messages: {len(smoke_test_messages)}")
        logger.info(f"   - Succeeded: {success_count}")
        logger.info(f"   - Failed: {failure_count}")
        logger.info("   - Regular message/send requests tested")
        return {
            "slug": definition.slug,
            "agent_name": final_agent_card_to_use.name,
            "base_url": base_url,
            "prompt_count": len(smoke_test_messages),
            "success_count": success_count,
            "failure_count": failure_count,
            "health_ok": True,
        }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Smoke test one or more A2A agents from the configured agents directory."
    )
    parser.add_argument(
        "--agent-slug",
        dest="agent_slug",
        default=None,
        help="Run smoke tests for only one agent slug.",
    )
    parser.add_argument(
        "--agent-config-dir",
        dest="agent_config_dir",
        default=None,
        help="Directory containing `*_agent.toml` files.",
    )
    parser.add_argument(
        "--base-url",
        dest="base_url",
        default=None,
        help=(
            "Public server base URL to test, for example "
            "`https://my-host.example.com`. The client will append `/<slug>`."
        ),
    )
    return parser.parse_args()


async def main() -> None:
    load_dotenv()
    load_dotenv(Path(__file__).resolve().with_name(".env"))
    args = _parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s  - %(message)s"
    )
    logger = logging.getLogger(__name__)

    definitions = load_agent_definitions(args.agent_config_dir)
    settings = load_server_settings()
    if args.base_url:
        logger.info("Using explicit base URL override: %s", args.base_url.rstrip("/"))
    selected_definitions = definitions
    if args.agent_slug:
        selected_definitions = tuple(
            definition
            for definition in definitions
            if definition.slug == args.agent_slug.strip().lower()
        )
        if not selected_definitions:
            raise ValueError(f"No agent with slug `{args.agent_slug}` was found.")

    logger.info("Loaded %s agent definitions for smoke testing.", len(definitions))
    logger.info("Running smoke tests for %s agent(s).", len(selected_definitions))

    summaries: list[dict[str, Any]] = []
    for definition in selected_definitions:
        logger.info("\n=== Smoke testing slug `%s` ===", definition.slug)
        summaries.append(
            await smoke_test_agent(
                definition,
                settings,
                logger,
                public_base_url_override=args.base_url,
            )
        )

    total_prompts = sum(summary["prompt_count"] for summary in summaries)
    total_successes = sum(summary["success_count"] for summary in summaries)
    total_failures = sum(summary["failure_count"] for summary in summaries)
    logger.info("\n=== Multi-Agent Smoke Test Summary ===")
    logger.info("Agents tested: %s", len(summaries))
    logger.info("Total prompts: %s", total_prompts)
    logger.info("Succeeded: %s", total_successes)
    logger.info("Failed: %s", total_failures)
    for summary in summaries:
        logger.info(
            " - %s (%s): %s/%s passed",
            summary["slug"],
            summary["agent_name"],
            summary["success_count"],
            summary["prompt_count"],
        )


if __name__ == "__main__":
    import asyncio

    print("A2A Agent Smoke Test Client")
    print("=" * 50)
    print("This client tests one or more configured A2A agents")
    print("using prompts from the discovered agent definitions.")
    print("Make sure the agent server is running first!")
    print("=" * 50)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Test client stopped by user")
    except Exception as e:
        print(f"\n❌ Test client failed: {e}")
        print("\n💡 Troubleshooting tips:")
        print("1. Ensure the A2A agent server is running")
        print("2. Check your .env configuration")
        print("3. Check your agents directory configuration")
        print("4. Check logs for detailed error information")
