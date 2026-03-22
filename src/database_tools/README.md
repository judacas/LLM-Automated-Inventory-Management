# Database Tools Module

## Overview

The `database_tools` module is the core data layer for the LLM-Automated Inventory Management system. It provides a structured architecture for integrating with an Azure SQL database while exposing business operations through an **MCP (Model Context Protocol) server**.

All operations are **email-based**, allowing AI agents to retrieve and manage customer data, quotes, inventory, and purchase orders using email addresses as the primary lookup key. This module bridges the gap between AI agents and the underlying database, providing:
- Database connection management
- Email-centric business logic encapsulation (Services)
- Tool interfaces for MCP exposure (Tools)
- Tool registry for dynamic tool lookup

---

## Folder Structure

```
database_tools/
├── database.py              # Database connection management
├── main.py                  # MCP server configuration and tool exposure
├── Dockerfile               # Container configuration
├── services/                # Business logic layer
│   ├── business_service.py  # Business account operations
│   ├── purchase_service.py  # Purchase order operations
│   ├── quote_service.py     # Quote and inventory operations
│   └── __init__.py
├── tools/                   # Tool wrappers for MCP exposure
│   ├── registry.py          # Tool registry (central lookup)
│   ├── business_tools.py    # Business account tool wrappers
│   ├── purchase_tools.py    # Purchase order tool wrappers
│   ├── quote_tools.py       # Quote and inventory tool wrappers
│   ├── __init__.py
│   └── __pycache__/
└── __pycache__/
```

---

## Component Descriptions

### 1. **database.py** - Connection Management
**Purpose**: Manages all database connectivity with Azure SQL.

**Key Function**:
- `get_connection()` - Establishes a pyODBC connection to Azure SQL Server using environment variables:
  - `AZURE_SQL_SERVER`
  - `AZURE_SQL_DATABASE`
  - `AZURE_SQL_USERNAME`
  - `AZURE_SQL_PASSWORD`

**Connection Details**:
- Uses ODBC Driver 18 for SQL Server
- Implements encryption and certificate validation
- 30-second connection timeout

---

### 2. **services/** - Business Logic Layer

This layer contains all domain-specific operations, separated by business concern:

#### **business_service.py**
Email-based operations related to business accounts.

**Key Components**:
- `BusinessAccount` (TypedDict) - Business account data structure with fields:
  - `account_id`, `company_name`, `address`, `business_type`, `billing_method`, `discount_percent`, `email`
- `create_business_account()` - Creates a new business account in the database identified by email
- `get_business_by_email(email)` - **Email-based lookup** - Retrieves a business account by email address
- `normalize_billing_method()` - Validates and normalizes billing methods (credit_card, mailed_invoice, wire_transfer, ach, bank_transfer)

#### **quote_service.py**
Email-based operations related to quotes and inventory management.

**Key Operations**:
- Quote Management (Email-Based):
  - `get_active_quotes_by_email(email)` - **Email-based lookup** - Retrieves active quotes for a specific customer
  - `get_quote_by_id()` - Retrieves quote details by ID
  - `confirm_quote()` - Confirms a quote and creates associated records
  - `confirm_quote_by_product_name()` - Confirms a quote using product name instead of ID
  - `expire_quotes()` - Handles quote expiration (valid for 5 days)
  - `get_outstanding_quotes()` - Retrieves all outstanding quotes

- Inventory Management:
  - `get_all_inventory()` - Retrieves complete product inventory
  - `get_inventory_status_by_name()` - Gets inventory status for a specific product
  - `get_out_of_stock_items()` - Retrieves all out-of-stock products
  - `get_product_id_by_name()` - Looks up product ID by product name

- Dashboard Metrics:
  - `get_dashboard_metrics()` - Provides business metrics and analytics
  - Returns: `DashboardMetricsResponse` with key statistics

**Data Models**:
- `QuoteSummary` - Summary of a quote
- `UserQuoteSummary` - User-specific quote information
- `InventoryItem` - Product with inventory details
- `InventoryStatusResponse` - Status of inventory
- `OutOfStockItem` - Out-of-stock product details
- `DashboardMetricsResponse` - Metrics and analytics

#### **purchase_service.py**
Email-based operations related to purchase orders.

**Key Operations**:
- `create_purchase_order(quote_id, email)` - Creates a purchase order from a quote, optionally associated with customer email
- `get_purchase_orders_by_email(email)` - **Email-based lookup** - Retrieves all purchase orders for a customer

**Data Models**:
- `CreatePurchaseOrderInput` - Input data for creating a purchase order (includes optional email)
- `PurchaseOrderResult` - Full purchase order with items detail
- `PurchaseOrderSummary` - Summary of a purchase order
- `PurchaseOrderItemResult` - Individual purchase order line item

---

### 3. **tools/** - MCP Tool Wrappers

This layer wraps service functions to expose them as MCP-compatible tools. Each tool is a simple wrapper that:
1. Accepts typed parameters
2. Calls the corresponding service function
3. Returns the result for MCP transport

#### **business_tools.py**
Email-aware wrappers for business account operations:
- `tool_create_business_account()` - Creates a business account with email
  - **Input**: `company_name` (str), `address` (str), `business_type` (str), `billing_method` (str), `email` (str)
  - **Output**: `int` - The created account ID
- `tool_get_business_by_email(email)` - **Email-based** - Retrieves business account by email
  - **Input**: `email` (str)
  - **Output**: `BusinessAccount | None` - Business account data or None if not found
    - Structure: `{account_id: int, company_name: str, address: str, business_type: str, billing_method: str, discount_percent: int, email: str}`

#### **quote_tools.py**
Email-aware wrappers for quote and inventory operations:
- `tool_get_product_id_by_name(name)` - Gets product ID
  - **Input**: `name` (str) - Product name
  - **Output**: `int` - The product ID
- `tool_confirm_quote_by_product_name(request)` - Confirms quote by product name
  - **Input**: `ConfirmQuoteByNameRequest` - `{email: str, items: [{name: str, quantity: int}]}`
  - **Output**: `ConfirmQuoteResponse` - `{quote_id: int, status: str, valid_until: date, total_amount: float, fulfillment: [fulfillment_items]}`
- `tool_confirm_quote(request)` - Confirms quote by product/quote ID
  - **Input**: `ConfirmQuoteRequest` - `{email: str, items: [{product_id: int, quantity: int}]}`
  - **Output**: `ConfirmQuoteResponse` - Same structure as above
- `tool_get_active_quotes(email)` - **Email-based** - Gets active quotes for a user
  - **Input**: `email` (str)
  - **Output**: `list[UserQuoteSummary]` - List of quote summaries: `{quote_id: int, created_at: str, valid_until: str, total_amount: float}`
- `tool_get_dashboard_metrics()` - Gets dashboard metrics
  - **Input**: None
  - **Output**: `DashboardMetricsResponse` - `{outstanding_quotes_count: int, outstanding_total_amount: float, out_of_stock_count: int}`
- `tool_get_outstanding_quotes()` - Gets outstanding quotes
  - **Input**: None
  - **Output**: `list[QuoteSummary]` - `{quote_id: int, account_id: int, status: str, created_at: str, valid_until: str, total_amount: float}`
- `tool_get_quote_by_id(quote_id)` - Gets quote details
  - **Input**: `quote_id` (int)
  - **Output**: `QuoteDetailResponse` - `{quote_id: int, account_id: int, status: str, created_at: str, valid_until: str, total_amount: float, line_items: [line_items]}`
- `tool_get_out_of_stock_items()` - Gets out-of-stock items
  - **Input**: None
  - **Output**: `list[OutOfStockItem]` - `{product_id: int, product_name: str, quantity_in_stock: int}`
- `tool_get_all_inventory()` - Gets all inventory
  - **Input**: None
  - **Output**: `list[InventoryItem]` - `{product_id: int, name: str, quantity_in_stock: int}`
- `tool_get_inventory_status(name)` - Gets inventory status for a product
  - **Input**: `name` (str) - Product name
  - **Output**: `InventoryStatusResponse` - `{product_id: int, name: str, quantity_in_stock: int, status: str}`

#### **purchase_tools.py**
Email-aware wrappers for purchase order operations:
- `tool_create_purchase_order(data)` - Creates a purchase order (includes optional email)
  - **Input**: `CreatePurchaseOrderInput` - `{quote_id: int, email: str | None}`
  - **Output**: `PurchaseOrderResult` - `{purchase_order_id: int, quote_id: int, account_id: int, status: str, total_amount: float, items: [order_items]}`
- `tool_get_purchase_orders(email)` - **Email-based** - Gets purchase orders by email
  - **Input**: `email` (str)
  - **Output**: `list[PurchaseOrderSummary]` - `{purchase_order_id: int, quote_id: int, status: str, created_at: str, total_amount: float}`

#### **registry.py**
Central registry for tool management.

**Key Class**: `MCPToolRegistry`
- `register(name, func)` - Registers a tool
- `get(name)` - Retrieves a tool by name
- `list_tools()` - Lists all available tools

**Pre-registered Tools**:
All service tools are pre-registered in the `registry` instance for easy lookup by name.

---

### 4. **main.py** - MCP Server & Tool Exposure

**Purpose**: Configures and runs the MCP server that exposes database tools to AI agents.

**Key Configurations**:
- **Server Name**: `SeniorProjectMCP`
- **Transport**: Stateless HTTP with FastAPI
- **Security**: 
  - DNS rebinding protection enabled
  - Allowed hosts: Azure App Service, localhost, 127.0.0.1
  - CORS configured for allowed origins

**Tool Exposure**:
Each service function is exposed as an MCP tool with:
- Decorated with `@mcp.tool()`
- Async wrapper for thread safety
- Proper type annotations
- Docstrings for tool discovery

**Example Tools Exposed**:
- Business management tools
- Quote and inventory queries
- Purchase order creation
- Dashboard metrics retrieval

---

## Architecture & Data Flow

```
┌─────────────────────────────────────────────────┐
│   AI Agents / LLM Applications                  │
└──────────────────┬──────────────────────────────┘
                   │ (HTTP/MCP Protocol)
                   ▼
┌─────────────────────────────────────────────────┐
│   main.py (MCP Server)                          │
│   - Exposes tools via FastAPI                   │
│   - Handles security & transport                │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│   tools/ (Tool Wrappers)                        │
│   - business_tools.py                           │
│   - quote_tools.py                              │
│   - purchase_tools.py                           │
│   - registry.py (lookup)                        │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│   services/ (Business Logic)                    │
│   - business_service.py                         │
│   - quote_service.py                            │
│   - purchase_service.py                         │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│   database.py (Connection Management)           │
│   - Azure SQL connectivity                      │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│   Azure SQL Database                            │
│   - Business accounts                           │
│   - Quotes & inventory                          │
│   - Purchase orders                             │
└─────────────────────────────────────────────────┘
```

---

## Deployment

### Docker Deployment
The module includes a `Dockerfile` for containerized deployment, suitable for:
- Azure Container Instances
- Azure App Service
- Kubernetes clusters

### Environment Variables Required
```
AZURE_SQL_SERVER=<server-name>.database.windows.net
AZURE_SQL_DATABASE=<database-name>
AZURE_SQL_USERNAME=<username>
AZURE_SQL_PASSWORD=<password>
```

---

## Design Patterns

### 1. **Separation of Concerns**
- **Services**: Pure business logic (database queries, calculations, email-based lookups)
- **Tools**: MCP-compatible wrappers (type conversion, error handling, email parameter passing)
- **Database**: Connection and configuration management

### 2. **Email-Centric Architecture**
- Customer data, quotes, and orders are accessed primarily via email addresses
- Email serves as the primary lookup key across services
- Enables agent-to-customer communication workflows

### 3. **Type Safety**
- Uses `TypedDict` for structured data (business_service.py)
- Type annotations throughout for IDE support and validation

### 4. **Registry Pattern**
- Centralized tool registry for dynamic tool lookup
- Allows programmatic discovery of available operations

### 5. **Async/Thread Safety**
- Tools use `asyncio.to_thread()` for thread-safe database access
- Enables concurrent tool invocations from MCP server

---
email-based tools from this module via MCP protocol
- Route customer requests (identified by email) to appropriate tools using the registry
- Combine tool results for complex multi-step operations
- Handle email-initiated workflows (quote requests, purchase orders, etc.)

### With Inventory Service
The `inventory_service` module can:
- Access inventory data through `quote_service` functions
- Sync inventory state between systems

### Email-Driven Workflows
- Agents use email addresses to identify customers and retrieve their data
- Operations are contextual to the customer's email address
- Supports multi-email scenarios for customer managementti-step operations

### With Inventory Service
The `inventory_service` module can:
- Access inventory data through `quote_service` functions
- Sync inventory state between systems

---

## Future Enhancements

- **Caching Layer**: Add Redis caching for frequently accessed inventory
- **Audit Logging**: Track all database operations for compliance
- **Connection Pooling**: Optimize database connection management
- **Query Analytics**: Monitor slow queries and optimize performance
