from contextlib import asynccontextmanager
from typing import AsyncIterator

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI

from mcp.routes.business_routes import router as business_router
from mcp.routes.quote_routes import router as quote_router
from mcp.services.quote_service import expire_quotes

scheduler = BackgroundScheduler()


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

app.include_router(business_router)
app.include_router(quote_router)
