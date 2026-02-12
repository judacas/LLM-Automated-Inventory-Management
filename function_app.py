import azure.functions as func

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


@app.function_name(name="hello")
@app.route(route="hello", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def hello(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse("hello from inventory-tool", status_code=200)
