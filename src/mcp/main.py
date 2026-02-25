from fastapi import FastAPI

from mcp.routes.business_routes import router as business_router

app = FastAPI()

app.include_router(business_router)
