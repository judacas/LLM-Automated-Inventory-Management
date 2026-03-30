from database_tools.services.quote_service import (
    ConfirmQuoteByNameRequest,
    ConfirmQuoteRequest,
    ConfirmQuoteResponse,
    InventoryItem,
    InventoryStatusResponse,
    OutOfStockItem,
    QuoteDetailResponse,
    QuoteSummary,
    RequestedUnavailableItem,
    UserQuoteSummary,
    confirm_quote,
    confirm_quote_by_product_name,
    get_active_quotes_by_email,
    get_all_inventory,
    get_inventory_status_by_name,
    get_out_of_stock_items,
    get_outstanding_quotes,
    get_product_id_by_name,
    get_quote_by_id,
    get_requested_unavailable_items,
)


def tool_get_product_id_by_name(name: str) -> int:
    return get_product_id_by_name(name)


def tool_confirm_quote_by_product_name(
    request: ConfirmQuoteByNameRequest,
) -> ConfirmQuoteResponse:
    return confirm_quote_by_product_name(request)


def tool_confirm_quote(request: ConfirmQuoteRequest) -> ConfirmQuoteResponse:
    return confirm_quote(request)


def tool_get_active_quotes(email: str) -> list[UserQuoteSummary]:
    return get_active_quotes_by_email(email=email)


def tool_get_outstanding_quotes() -> list[QuoteSummary]:
    return get_outstanding_quotes()


def tool_get_quote_by_id(quote_id: int) -> QuoteDetailResponse:
    return get_quote_by_id(quote_id=quote_id)


def tool_get_out_of_stock_items() -> list[OutOfStockItem]:
    return get_out_of_stock_items()


def tool_get_all_inventory() -> list[InventoryItem]:
    return get_all_inventory()


def tool_get_inventory_status(name: str) -> InventoryStatusResponse:
    return get_inventory_status_by_name(name=name)


def tool_get_requested_unavailable_items() -> list[RequestedUnavailableItem]:
    return get_requested_unavailable_items()
