import asyncio
from contextlib import AsyncExitStack, asynccontextmanager
from typing import AsyncIterator

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from database_tools.services.business_service import (
    BusinessAccount,
    create_business_account,
    get_business_by_domain,
)
from database_tools.services.purchase_service import (
    CreatePurchaseOrderInput,
    PurchaseOrderResult,
    PurchaseOrderSummary,
    create_purchase_order,
    get_purchase_orders_by_domain,
)
from database_tools.services.quote_service import (
    ConfirmQuoteByNameRequest,
    ConfirmQuoteRequest,
    ConfirmQuoteResponse,
    DashboardMetricsResponse,
    InventoryItem,
    InventoryStatusResponse,
    OutOfStockItem,
    QuoteDetailResponse,
    QuoteSummary,
    UserQuoteSummary,
    confirm_quote,
    confirm_quote_by_product_name,
    expire_quotes,
    get_active_quotes_by_domain,
    get_all_inventory,
    get_dashboard_metrics,
    get_inventory_status_by_name,
    get_out_of_stock_items,
    get_outstanding_quotes,
    get_product_id_by_name,
    get_quote_by_id,
)

scheduler = BackgroundScheduler()

mcp = FastMCP(
    name="SeniorProjectMCP",
    stateless_http=True,
    json_response=True,
    streamable_http_path="/",
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[
            "seniorproject-mcp-container.azurewebsites.net",
            "localhost:*",
            "127.0.0.1:*",
        ],
        allowed_origins=[
            "https://seniorproject-mcp-container.azurewebsites.net",
            "http://localhost:*",
            "http://127.0.0.1:*",
        ],
    ),
)


@mcp.tool()
async def get_business_by_domain_tool(domain: str) -> BusinessAccount | None:
    """
    Look up a business account by its domain and return the business record,
    or None if no matching business exists.
    """
    return await asyncio.to_thread(get_business_by_domain, domain)


@mcp.tool()
async def create_business_account_tool(
    company_name: str,
    address: str,
    business_type: str,
    billing_method: str,
    domain: str,
    authorized_emails: list[str],
) -> int:
    """
    Create a new business account and return the created account ID.
    """
    return await asyncio.to_thread(
        create_business_account,
        company_name,
        address,
        business_type,
        billing_method,
        domain,
        authorized_emails,
    )


@mcp.tool()
async def get_product_id_by_name_tool(name: str) -> int:
    """
    Resolve a product name to its product ID.
    """
    return await asyncio.to_thread(get_product_id_by_name, name)


@mcp.tool()
async def confirm_quote_by_product_name_tool(
    request: ConfirmQuoteByNameRequest,
) -> ConfirmQuoteResponse:
    """
    Create a quote using product names instead of product IDs.
    """
    return await asyncio.to_thread(confirm_quote_by_product_name, request)


@mcp.tool()
async def get_active_quotes_tool(domain: str) -> list[UserQuoteSummary]:
    """
    Return all active quotes for the business associated with the given domain.
    """
    return await asyncio.to_thread(get_active_quotes_by_domain, domain)


@mcp.tool()
async def get_quote_by_id_tool(quote_id: int) -> QuoteDetailResponse:
    """
    Return full details for a specific quote by quote ID.
    """
    return await asyncio.to_thread(get_quote_by_id, quote_id)


@mcp.tool()
async def get_inventory_status_tool(name: str) -> InventoryStatusResponse:
    """
    Return inventory status for a product by product name.
    """
    return await asyncio.to_thread(get_inventory_status_by_name, name)


@mcp.tool()
async def get_dashboard_metrics_tool() -> DashboardMetricsResponse:
    """
    Return dashboard metrics for active quotes and out-of-stock inventory.
    """
    return await asyncio.to_thread(get_dashboard_metrics)


@mcp.tool()
async def get_outstanding_quotes_tool() -> list[QuoteSummary]:
    """
    Return all currently active outstanding quotes.
    """
    return await asyncio.to_thread(get_outstanding_quotes)


@mcp.tool()
async def get_out_of_stock_items_tool() -> list[OutOfStockItem]:
    """
    Return all inventory items that are currently out of stock.
    """
    return await asyncio.to_thread(get_out_of_stock_items)


@mcp.tool()
async def get_all_inventory_tool() -> list[InventoryItem]:
    """
    Return all inventory items and their current stock counts.
    """
    return await asyncio.to_thread(get_all_inventory)


@mcp.tool()
async def confirm_quote_tool(request: ConfirmQuoteRequest) -> ConfirmQuoteResponse:
    """
    Create a quote for a business account and return quote details including
    fulfillment information.
    """
    return await asyncio.to_thread(confirm_quote, request)


@mcp.tool()
async def get_purchase_orders_tool(domain: str) -> list[PurchaseOrderSummary]:
    """
    Return all purchase orders for the business associated with the given domain.
    """
    return await asyncio.to_thread(get_purchase_orders_by_domain, domain)


@mcp.tool()
async def create_purchase_order_tool(
    data: CreatePurchaseOrderInput,
) -> PurchaseOrderResult:
    """
    Convert an active quote into a purchase order and return the created purchase order details.
    """
    return await asyncio.to_thread(create_purchase_order, data)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with AsyncExitStack() as stack:
        await stack.enter_async_context(mcp.session_manager.run())

        scheduler.add_job(
            expire_quotes,
            trigger="cron",
            hour=2,
            minute=0,
            id="expire_quotes_daily",
            replace_existing=True,
        )
        scheduler.start()

        try:
            yield
        finally:
            if scheduler.running:
                scheduler.shutdown()


app = FastAPI(lifespan=lifespan)

app.mount("/mcp", mcp.streamable_http_app())


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
