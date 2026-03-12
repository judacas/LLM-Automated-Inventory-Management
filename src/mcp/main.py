from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from mcp.services.quote_service import expire_quotes
from mcp.tools.registry import registry

scheduler = BackgroundScheduler()


class MCPRequest(BaseModel):
    tool: str
    arguments: dict[str, Any] = {}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Startup logic
    scheduler.add_job(
        expire_quotes,
        trigger="cron",
        hour=2,
        minute=0,
    )
    scheduler.start()

    yield

    # Shutdown logic
    scheduler.shutdown()


app = FastAPI(lifespan=lifespan)


@app.post("/mcp")
async def handle_mcp(body: MCPRequest) -> Any:
    """
    MCP tool execution endpoint.

    Example request:
    {
        "tool": "confirm_quote",
        "arguments": {...}
    }
    """

    tool_name = body.tool
    arguments = body.arguments

    if not tool_name:
        raise HTTPException(status_code=400, detail="Tool name missing")

    try:
        tool = registry.get(tool_name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    try:
        result = tool(arguments)
        return {"result": result}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/mcp/tools")
def list_mcp_tools() -> dict[str, list[str]]:
    return {"tools": registry.list_tools()}
