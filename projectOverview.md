# Contoso Automated Customer Service – Project Requirements

## Overview

Design, develop, and deploy a set of AI agents that automate customer service for a fictional company, **Contoso**.  
The solution must leverage:

- **LLMs**
- **Multi-agent architecture**
- **A2A (Agent-to-Agent) communication**
- **MCP (Model Context Protocol)**

At least one agent must expose a **conversational interface** for human interaction.

---

## Functional Requirements

### 1. Customer Quote & Purchase Flow (Email-Based)

Customers must be able to initiate actions by sending an email.

#### 1.1 Request a Quote

- Customers can request a quote for items Contoso sells.
- Contoso has **20 products**, each with one of the following availability states:
  - In stock
  - Available on a specific future date
  - Out of stock (unknown availability)

#### 1.2 Purchase Order Option

- As part of the quote, the system must ask whether the customer wants to proceed with a **purchase order**.
- If the customer agrees:
  - Create a purchase order
  - Send an invoice
  - Notify the shipping department

#### 1.3 Quote Persistence

- If the customer does **not** proceed with a purchase:
  - The quote is saved
  - Quotes remain valid for **5 days**
  - Each customer may have up to **5 saved quotes**
  - Customers can later request saved quotes to complete a purchase

---

### 2. Inventory Management

The system must maintain an up-to-date inventory database.

#### 2.1 Inventory Updates

- Inventory must update based on:
  - Purchase order activity
  - Incoming shipments (which may occur at any time)

#### 2.2 Availability Rules

- Purchase orders must:
  - Reduce availability of in-stock items
  - Reduce future availability for items not yet in stock

---

### 3. Customer Onboarding

If a quote request comes from an **unknown email domain**, the system must onboard the customer **before** delivering the quote.

#### 3.1 Required Business Information

During onboarding, collect:

- Business name
- Business address
- Type of business
- Authorized email addresses for completing purchase orders
- Preferred billing method:
  - Credit card
  - Mailed invoice

#### 3.2 Billing Rules

- Customers using **immediate credit card billing** receive a **5% discount**
- The discount must appear as a **line item on quotes**

#### 3.3 Authorization Rules

- After onboarding:
  - Any employee of the customer may request quotes
  - Only authorized emails may proceed to purchase orders

---

### 4. Administrator Conversational Interface

Provide a conversational interface for Contoso administrators.

Admins must be able to view:

- Number of outstanding quotes
- Total dollar amount of outstanding quotes
- Items requested by customers that are currently unavailable
- General system and inventory status

---

## Technology & Compliance Requirements

### 5. Required Technologies

The project must incorporate:

- Azure cloud resources (compute, storage, networking)
- Azure AI Foundry and/or Azure OpenAI
- Copilot Studio (as appropriate)
- Microsoft documentation and learning resources

### 6. Budget Constraints

- Cloud resource usage must not exceed **$150 per month**
- Usage must remain strictly within the scope of this project

### 7. Data & Security Compliance

- All generated data must comply with applicable regulations (including **FERPA**)
- Access to Azure resources must be restricted to the project team only
- Resources may be shared with USF staff or students **only** for user acceptance testing
- Unauthorized or inappropriate use may result in loss of access

---

## Team Communication Requirements

### 8. Collaboration Expectations

The team must:

- Meet at least **once per week** for **30 minutes**
- Communicate critical issues via email or Teams
- Share key documents with sponsors and faculty
- Delegate work effectively and fairly among team members
