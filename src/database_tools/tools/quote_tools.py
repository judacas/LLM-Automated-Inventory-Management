from typing import Any, TypedDict

from mcp.services.quote_service import (
    ConfirmQuoteRequest,
    confirm_quote,
    get_active_quotes_by_domain,
    get_all_inventory,
    get_dashboard_metrics,
    get_inventory_status_by_name,
    get_out_of_stock_items,
    get_outstanding_quotes,
    get_quote_by_id,
    get_quotes_by_email,
)


class DomainArgs(TypedDict):
    domain: str


class EmailArgs(TypedDict):
    email: str


class QuoteIdArgs(TypedDict):
    quote_id: int


class ProductNameArgs(TypedDict):
    name: str


def tool_confirm_quote(arguments: ConfirmQuoteRequest) -> Any:
    return confirm_quote(arguments)


def tool_get_active_quotes(arguments: DomainArgs) -> Any:
    return get_active_quotes_by_domain(
        domain=arguments["domain"],
    )


def tool_get_dashboard_metrics(arguments: dict[str, object]) -> Any:
    return get_dashboard_metrics()


def tool_get_outstanding_quotes(arguments: dict[str, object]) -> Any:
    return get_outstanding_quotes()


def tool_get_quotes_by_email(arguments: EmailArgs) -> Any:
    return get_quotes_by_email(
        email=arguments["email"],
    )


def tool_get_quote_by_id(arguments: QuoteIdArgs) -> Any:
    return get_quote_by_id(
        quote_id=arguments["quote_id"],
    )


def tool_get_out_of_stock_items(arguments: dict[str, object]) -> Any:
    return get_out_of_stock_items()


def tool_get_all_inventory(arguments: dict[str, object]) -> Any:
    return get_all_inventory()


def tool_get_inventory_status(arguments: ProductNameArgs) -> Any:
    return get_inventory_status_by_name(
        name=arguments["name"],
    )
