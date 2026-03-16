import asyncio
from contextlib import AsyncExitStack, asynccontextmanager
from typing import AsyncIterator

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from mcp.server.fastmcp import FastMCP

from database_tools.services.business_service import (
    BusinessAccount,
    get_business_by_domain,
)
from database_tools.services.quote_service import expire_quotes

scheduler = BackgroundScheduler()

mcp = FastMCP(
    name="SeniorProjectMCP",
    stateless_http=True,
    json_response=True,
    streamable_http_path="/",
)


@mcp.tool()
async def get_business_by_domain_tool(domain: str) -> BusinessAccount | None:
    """
    Look up a business account by its email/domain and return the business record,
    or None if no matching business exists.
    """
    return await asyncio.to_thread(get_business_by_domain, domain)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with AsyncExitStack() as stack:
        await stack.enter_async_context(mcp.session_manager.run())

        scheduler.add_job(
            expire_quotes,
            trigger="cron",
            hour=2,
            minute=0,
            id="expire_quotes_daily",
            replace_existing=True,
        )
        scheduler.start()

        try:
            yield
        finally:
            if scheduler.running:
                scheduler.shutdown()


app = FastAPI(lifespan=lifespan)

app.mount("/mcp", mcp.streamable_http_app())


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
