import os

from inventory_service.factory import build_inventory_service


def test_factory_builds_without_connection_string() -> None:
    old = os.environ.pop("AZURE_SQL_CONNECTION_STRING", None)
    try:
        svc = build_inventory_service()
        assert svc is not None
    finally:
        if old is not None:
            os.environ["AZURE_SQL_CONNECTION_STRING"] = old


def test_factory_builds_with_connection_string_set() -> None:
    old = os.environ.get("AZURE_SQL_CONNECTION_STRING")
    try:
        # dummy string: we are NOT calling repo methods here
        os.environ["AZURE_SQL_CONNECTION_STRING"] = (
            "Driver={ODBC Driver 18 for SQL Server};Server=tcp:example.database.windows.net,1433;Database=db;Uid=u;Pwd=p;Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
        )
        svc = build_inventory_service()
        assert svc is not None
    finally:
        if old is None:
            os.environ.pop("AZURE_SQL_CONNECTION_STRING", None)
        else:
            os.environ["AZURE_SQL_CONNECTION_STRING"] = old
