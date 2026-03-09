from fastapi import APIRouter, HTTPException

from mcp.services.quote_service import (
    # Contracts
    ConfirmQuoteRequest,
    ConfirmQuoteResponse,
    DashboardMetricsResponse,
    InventoryItem,
    InventoryStatusResponse,
    OutOfStockItem,
    QuoteDetailResponse,
    QuoteSummary,
    UserQuoteSummary,
    # User-side services
    confirm_quote,
    get_active_quotes_by_domain,
    # Admin-side services
    get_all_inventory,
    get_dashboard_metrics,
    get_inventory_status_by_name,
    get_out_of_stock_items,
    get_outstanding_quotes,
    get_quote_by_id,
    get_quotes_by_email,
)

router = APIRouter(prefix="/quotes", tags=["Quotes"])


# =========================
# USER-SIDE ROUTES
# =========================


@router.post("/confirm", response_model=ConfirmQuoteResponse)
def confirm(request: ConfirmQuoteRequest) -> ConfirmQuoteResponse:
    try:
        return confirm_quote(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/active", response_model=list[UserQuoteSummary])
def active_quotes(domain: str) -> list[UserQuoteSummary]:
    try:
        return get_active_quotes_by_domain(domain)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/inventory/status", response_model=InventoryStatusResponse)
def inventory_status(name: str) -> InventoryStatusResponse:
    try:
        return get_inventory_status_by_name(name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# =========================
# ADMIN-SIDE ROUTES
# =========================


@router.get("/admin/dashboard", response_model=DashboardMetricsResponse)
def dashboard() -> DashboardMetricsResponse:
    return get_dashboard_metrics()


@router.get("/admin/outstanding", response_model=list[QuoteSummary])
def outstanding() -> list[QuoteSummary]:
    return get_outstanding_quotes()


@router.get("/admin/by-email", response_model=list[QuoteSummary])
def by_email(email: str) -> list[QuoteSummary]:
    return get_quotes_by_email(email)


@router.get("/admin/out-of-stock", response_model=list[OutOfStockItem])
def out_of_stock() -> list[OutOfStockItem]:
    return get_out_of_stock_items()


@router.get("/admin/inventory", response_model=list[InventoryItem])
def inventory() -> list[InventoryItem]:
    return get_all_inventory()


@router.get("/admin/{quote_id}", response_model=QuoteDetailResponse)
def quote_detail(quote_id: int) -> QuoteDetailResponse:
    try:
        return get_quote_by_id(quote_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
