# Database Tools Module

## Overview

The `database_tools` module serves as the core data layer for the LLM-Automated Inventory Management system. It provides a robust architecture for integrating with an Azure SQL database and exposes business operations through an **MCP (Model Context Protocol) server**.

All operations are **email-based**, enabling AI agents to retrieve and manage customer data, quotes, inventory, and purchase orders using email addresses as the primary identifier. This module acts as a bridge between AI agents and the database, offering:

- Secure database connection management
- Email-centric business logic encapsulation
- MCP-compatible tool interfaces
- Dynamic tool registry for efficient lookups

## Folder Structure

```text
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

## Components

### 1. database.py - Connection Management

**Purpose**: Handles all database connectivity to Azure SQL.

**Key Function**:

- `get_connection()`: Establishes a secure pyODBC connection using environment variables:
  - `AZURE_SQL_SERVER`
  - `AZURE_SQL_DATABASE`
  - `AZURE_SQL_USERNAME`
  - `AZURE_SQL_PASSWORD`

**Connection Features**:

- ODBC Driver 18 for SQL Server
- Encryption and certificate validation enabled
- 30-second connection timeout

### 2. services/ - Business Logic Layer

Contains email-specific operations organized by business domain:

#### business_service.py

Handles business account operations:

- `BusinessAccount` TypedDict: Defines account structure with fields like `account_id`, `company_name`, `email`, etc.
- `create_business_account()`: Creates new accounts identified by email
- `get_business_by_email(email)`: Retrieves accounts via email lookup
- `normalize_billing_method()`: Validates billing methods (credit_card, mailed_invoice, etc.)

#### quote_service.py

Manages quotes and inventory:

- **Quote Operations**: `get_active_quotes_by_email()`, `confirm_quote()`, `expire_quotes()`
- **Inventory Operations**: `get_all_inventory()`, `get_inventory_status_by_name()`, `get_out_of_stock_items()`
- **Analytics**: `get_dashboard_metrics()` for business insights

#### purchase_service.py

Handles purchase orders:

- `create_purchase_order()`: Creates orders from quotes with optional email association
- `get_purchase_orders_by_email()`: Email-based order retrieval

### 3. tools/ - MCP Tool Wrappers

Wraps service functions for MCP compatibility:

#### business_tools.py

- `tool_create_business_account()`: Creates accounts with email
- `tool_get_business_by_email()`: Email-based account lookup

#### quote_tools.py

- `tool_confirm_quote_by_product_name()`: Confirms quotes using product names
- `tool_get_active_quotes()`: Retrieves user quotes by email
- `tool_get_dashboard_metrics()`: Provides business metrics
- `tool_get_all_inventory()`: Lists all products

#### purchase_tools.py

- `tool_create_purchase_order()`: Creates purchase orders
- `tool_get_purchase_orders()`: Email-based order retrieval

#### registry.py

Central tool management:

- `MCPToolRegistry` class for registering and discovering tools
- Pre-registered tools for easy access

### 4. main.py - MCP Server

**Purpose**: Runs the MCP server exposing database tools to AI agents.

**Configuration**:

- Server Name: `SeniorProjectMCP`
- Transport: Stateless HTTP via FastAPI
- Security: DNS rebinding protection, CORS, allowed hosts

**Tool Exposure**: Each service function becomes an MCP tool with async wrappers for thread safety.

## Architecture & Data Flow

```text
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

## Deployment

### Docker Deployment

Includes a `Dockerfile` for containerized deployment on:

- Azure Container Instances
- Azure App Service
- Kubernetes clusters

### Required Environment Variables

```text
AZURE_SQL_SERVER=<server-name>.database.windows.net
AZURE_SQL_DATABASE=<database-name>
AZURE_SQL_USERNAME=<username>
AZURE_SQL_PASSWORD=<password>
```

## Design Patterns

### Separation of Concerns

- **Services**: Pure business logic and database queries
- **Tools**: MCP wrappers with type conversion and error handling
- **Database**: Connection and configuration management

### Email-Centric Design

- Email as primary lookup key for customer operations
- Enables seamless agent-to-customer workflows
- Supports multi-email customer management

### Type Safety & Registry

- TypedDict structures for data validation
- Centralized tool registry for dynamic discovery
- Async operations for concurrent access

## Integration

### With A2A Servers

- Agents access email-based tools via MCP protocol
- Route customer requests using the tool registry
- Handle complex multi-step operations

### With Inventory Service

- Sync inventory data through quote_service functions
- Maintain consistent state across systems

## Future Enhancements

- **Caching Layer**: Redis for frequently accessed data
- **Audit Logging**: Track operations for compliance
- **Connection Pooling**: Optimize database performance
- **Query Analytics**: Monitor and optimize slow queries
