import os
import sys

import azure.functions as func
from azure.functions import AsgiMiddleware

# Make src/ importable BEFORE importing your FastAPI app
ROOT = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(ROOT, "src"))

from tool_api.app import app as fastapi_app  # noqa: E402

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


@app.function_name(name="api")
@app.route(
    route="{*path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
def api(req: func.HttpRequest, context: func.Context) -> func.HttpResponse:
    # Route all /api/* requests into FastAPI
    return AsgiMiddleware(fastapi_app).handle(req, context)
