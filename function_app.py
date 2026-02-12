import os

import azure.functions as func
from azure.functions import AsgiMiddleware

# Ensure src/ is importable
os.environ.setdefault("PYTHONPATH", "src")

from tool_api.app import app as fastapi_app

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)
app = AsgiMiddleware(app, fastapi_app).main
