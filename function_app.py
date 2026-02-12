import os

import azure.functions as func

# Ensure src/ is importable (because your FastAPI code lives under src/)
os.environ.setdefault("PYTHONPATH", "src")

from tool_api.app import app as fastapi_app

# This exposes your FastAPI app as an HTTP-triggered Azure Function under /api/*
app = func.AsgiFunctionApp(
    app=fastapi_app,
    http_auth_level=func.AuthLevel.ANONYMOUS,
)
