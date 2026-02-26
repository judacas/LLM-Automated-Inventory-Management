from fastapi import FastAPI

from mcp.routes.business_routes import router as business_router
from mcp.routes.inventory_routes import router as inventory_router

app = FastAPI()

app.include_router(business_router)
app.include_router(inventory_router)
