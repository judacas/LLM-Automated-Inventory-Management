// server.js
require('dotenv').config();

// Ensure telemetry starts before any other imports so it auto-instruments express & winston
const { useAzureMonitor } = require("@azure/monitor-opentelemetry");
if (process.env.APPLICATIONINSIGHTS_CONNECTION_STRING) {
  try {
    useAzureMonitor();
    console.log("[Observability] Azure Monitor OpenTelemetry initialized successfully.");
  } catch (err) {
    console.error("[Observability] Failed to start Azure Monitor:", err);
  }
} else {
  console.log("[Observability] No APPLICATIONINSIGHTS_CONNECTION_STRING found. Running without distributed tracing.");
}

const {
  createConversation,
  sendMessageToAgent,
} = require("./utils/foundryClient");

const express = require('express');
const cookieParser = require('cookie-parser');
const jwt = require('jsonwebtoken');
const path = require('path');
const crypto = require('crypto');
const sql = require('mssql');
const { DefaultAzureCredential, AzureCliCredential, ChainedTokenCredential } = require('@azure/identity');
const { LogsQueryClient } = require('@azure/monitor-query');
const logger = require('./utils/logger');

const app = express();
const PORT = process.env.PORT || 3000;
const JWT_SECRET = process.env.JWT_SECRET;

// Hard-coded admin credentials
const ADMIN_USERNAME = 'admin';
const ADMIN_PASSWORD = 'contoso123';

app.use(express.json());
app.use(cookieParser());
app.use(express.static(path.join(__dirname, 'public')));

// Middleware to check auth
function authenticateToken(req, res, next) {
  const token = req.cookies.token;
  if (!token) {
    logger.warn('Unauthorized access attempt');
    return res.status(401).send('Unauthorized');
  }

  jwt.verify(token, JWT_SECRET, (err, user) => {
    if (err) {
      logger.warn('Invalid JWT token');
      return res.status(403).send('Forbidden');
    }
    req.user = user;
    next();
  });
}

// ===== Routes ===== //

function extractAgentTextFromResponse(response) {
  // Prefer output_text when available; it is typically the canonical, already-assembled text.
  // Combining it with parsed output items can lead to duplicated content.
  if (typeof response?.output_text === 'string') {
    const trimmed = response.output_text.trim();
    if (trimmed) return trimmed;
  }

  const parts = [];

  const out = response?.output;
  if (Array.isArray(out)) {
    for (const item of out) {
      if (item?.type !== 'message') continue;
      const content = item?.content;
      if (!Array.isArray(content)) continue;

      for (const chunk of content) {
        // Azure AI Projects / Responses API can use output_text, text, or refusal.
        if (typeof chunk?.text === 'string') {
          parts.push(chunk.text);
          continue;
        }
        if (chunk?.type === 'output_text' && typeof chunk?.text === 'string') {
          parts.push(chunk.text);
          continue;
        }
        if (chunk?.type === 'text' && typeof chunk?.text === 'string') {
          parts.push(chunk.text);
          continue;
        }
        if (chunk?.type === 'refusal' && typeof chunk?.refusal === 'string') {
          parts.push(chunk.refusal);
          continue;
        }
      }
    }
  }

  return parts
    .map((p) => String(p))
    .join('\n')
    .trim();
}

function summarizeFoundryResponse(response) {
  const out = response?.output;
  const types = [];

  if (Array.isArray(out)) {
    for (const item of out) {
      if (item?.type) types.push(item.type);
    }
  }

  return {
    hasOutputText: typeof response?.output_text === 'string',
    outputItems: Array.isArray(out) ? out.length : 0,
    outputTypes: [...new Set(types)],
  };
}

// Login endpoint
app.post('/auth/login', (req, res) => {
  const { username, password } = req.body;
  logger.info(`Login attempt for user: ${username}`);
  
  if (username === ADMIN_USERNAME && password === ADMIN_PASSWORD) {
    const token = jwt.sign({ username }, JWT_SECRET, { expiresIn: '1h' });
    res.cookie('token', token, { httpOnly: true });
    logger.info(`Login SUCCESS for user: ${username}`);
    return res.json({ success: true, message: `Welcome, ${username}!` });
  } else {
    logger.warn(`Login FAILED for user: ${username}`);
    return res.json({ success: false, error: 'Invalid credentials' });
  }
});

// Logout
app.post('/auth/logout', (req, res) => {
  res.clearCookie('token');
  res.clearCookie('conversationId');
  logger.info('User logged out');
  res.json({ success: true });
});

app.post('/admin/chat', authenticateToken, async (req, res) => {
  const { message } = req.body;
  const requestId = req.get('x-request-id') || crypto.randomUUID();
  const startedAt = Date.now();
  logger.info(`[${requestId}] Admin chat from ${req.user.username}: ${message}`);

  if (!message || !message.trim()) {
    return res.status(400).json({
      success: false,
      error: 'Message is required',
      requestId,
    });
  }

  try {
    let conversationId = req.cookies.conversationId;
    let newConversation = false;

    // Create one conversation per logged-in browser session
    if (!conversationId) {
      const conversation = await createConversation();
      conversationId = conversation.id;
      newConversation = true;

      res.cookie('conversationId', conversationId, {
        httpOnly: true,
        sameSite: 'lax'
      });

      logger.info(`[${requestId}] Created Foundry conversation: ${conversationId}`);
    }

    const response = await sendMessageToAgent({
      conversationId,
      message
    });

    const extracted = extractAgentTextFromResponse(response);
    const durationMs = Date.now() - startedAt;
    const isDebug = req.get('x-client-debug') === '1';
    const responseSummary = summarizeFoundryResponse(response);

    if (!extracted) {
      logger.warn(`[${requestId}] Foundry returned empty text output (${durationMs}ms): ${JSON.stringify(responseSummary)}`);
      return res.json({
        success: true,
        empty: true,
        reply: '',
        requestId,
        ...(isDebug && { debug: { conversationId, durationMs, newConversation, outputSummary: responseSummary, replyChars: 0 } }),
      });
    }

    logger.info(`[${requestId}] Admin chat success (${durationMs}ms, chars=${extracted.length})`);
    if (isDebug) {
      logger.info(
        `[${requestId}] [DEBUG] conversationId=${conversationId} ` +
        `newConversation=${newConversation} durationMs=${durationMs} ` +
        `chars=${extracted.length} outputItems=${responseSummary.outputItems} ` +
        `outputTypes=${JSON.stringify(responseSummary.outputTypes)}`
      );
    }
    return res.json({
      success: true,
      reply: extracted,
      requestId,
      ...(isDebug && { debug: { conversationId, durationMs, newConversation, outputSummary: responseSummary, replyChars: extracted.length } }),
    });
  } catch (err) {
    const durationMs = Date.now() - startedAt;
    const errMsg = String(err?.message || err);
    logger.error(`[${requestId}] Admin chat error (${durationMs}ms): ${err?.stack || errMsg}`);

    // Rate limit from Foundry — clear the conversation so the next message starts fresh.
    // The accumulated tool-call context in long conversations is the most common cause.
    if (errMsg.includes('429') || errMsg.toLowerCase().includes('too many requests')) {
      res.clearCookie('conversationId');
      logger.warn(`[${requestId}] Rate limited by Foundry — conversation cookie cleared, next message will start a fresh conversation`);
      return res.status(429).json({
        success: false,
        error: 'Rate limit reached — the conversation was too long. It has been reset automatically. Wait a moment and resend your message.',
        requestId,
        conversationReset: true,
      });
    }

    // MCP tool approval required — clear, non-scary message.
    if (errMsg.toLowerCase().includes('requires approval')) {
      return res.status(409).json({
        success: false,
        error: `${errMsg} (Approve it in Foundry portal, then retry.)`,
        requestId,
      });
    }

    return res.status(500).json({
      success: false,
      error: 'Failed to process admin chat request.',
      requestId,
    });
  }
});

// Protect dashboard.html itself (prevents direct access without cookie)
app.get('/dashboard.html', authenticateToken, (req, res) => {
  logger.info(`dashboard.html served to: ${req.user.username}`);
  res.sendFile(path.join(__dirname, 'public', 'dashboard.html'));
});

/**
 * Base URL for the MCP FastAPI quote routes. MCP_BASE_URL is often set to .../mcp for
 * documentation, but uvicorn serves /quotes/... at the site root, not under /mcp.
 */
function mcpQuotesApiBase() {
  const raw = (process.env.MCP_BASE_URL || '').trim();
  if (!raw) return '';
  return raw.replace(/\/$/, '').replace(/\/mcp$/i, '');
}

function buildSqlConfig() {
  const user = process.env.AZURE_SQL_USERNAME;
  const password = process.env.AZURE_SQL_PASSWORD;
  const database = process.env.AZURE_SQL_DATABASE;
  const server = process.env.AZURE_SQL_SERVER;
  if (!user || password === undefined || password === '' || !database || !server) {
    return null;
  }
  return {
    user,
    password,
    database,
    server,
    options: { encrypt: true, trustServerCertificate: false },
  };
}

async function ensureResponseEvaluationsTable(pool) {
  await pool.request().query(`
    IF OBJECT_ID('dbo.response_evaluations', 'U') IS NULL
    BEGIN
      CREATE TABLE dbo.response_evaluations (
        id INT IDENTITY(1,1) PRIMARY KEY,
        response_log_id INT NULL,
        customer_email NVARCHAR(255) NULL,
        customer_subject NVARCHAR(500) NULL,
        customer_email_body NVARCHAR(MAX) NOT NULL,
        final_system_response NVARCHAR(MAX) NOT NULL,
        agent_name NVARCHAR(100) NULL,
        classification NVARCHAR(20) NULL,
        confidence_score FLOAT NULL,
        evaluator_source NVARCHAR(50) NOT NULL DEFAULT 'Manual',
        expected_behavior NVARCHAR(MAX) NULL,
        true_label NVARCHAR(50) NULL,
        predicted_label NVARCHAR(50) NULL,
        review_notes NVARCHAR(MAX) NULL,
        reviewed_by NVARCHAR(100) NULL,
        reviewed_at DATETIME2 NULL,
        created_at DATETIME2 DEFAULT SYSUTCDATETIME()
      );
    END
  `);

  // Schema drift protection: if table already existed from an older version,
  // add any missing columns required by the current dashboard/API.
  await pool.request().query(`
    IF COL_LENGTH('dbo.response_evaluations', 'response_log_id') IS NULL
      ALTER TABLE dbo.response_evaluations ADD response_log_id INT NULL;
    IF COL_LENGTH('dbo.response_evaluations', 'customer_email') IS NULL
      ALTER TABLE dbo.response_evaluations ADD customer_email NVARCHAR(255) NULL;
    IF COL_LENGTH('dbo.response_evaluations', 'customer_subject') IS NULL
      ALTER TABLE dbo.response_evaluations ADD customer_subject NVARCHAR(500) NULL;
    IF COL_LENGTH('dbo.response_evaluations', 'customer_email_body') IS NULL
      ALTER TABLE dbo.response_evaluations ADD customer_email_body NVARCHAR(MAX) NULL;
    IF COL_LENGTH('dbo.response_evaluations', 'final_system_response') IS NULL
      ALTER TABLE dbo.response_evaluations ADD final_system_response NVARCHAR(MAX) NULL;
    IF COL_LENGTH('dbo.response_evaluations', 'agent_name') IS NULL
      ALTER TABLE dbo.response_evaluations ADD agent_name NVARCHAR(100) NULL;
    IF COL_LENGTH('dbo.response_evaluations', 'classification') IS NULL
      ALTER TABLE dbo.response_evaluations ADD classification NVARCHAR(20) NULL;
    IF COL_LENGTH('dbo.response_evaluations', 'confidence_score') IS NULL
      ALTER TABLE dbo.response_evaluations ADD confidence_score FLOAT NULL;
    IF COL_LENGTH('dbo.response_evaluations', 'evaluator_source') IS NULL
      ALTER TABLE dbo.response_evaluations ADD evaluator_source NVARCHAR(50) NOT NULL CONSTRAINT DF_response_evaluations_evaluator_source DEFAULT 'Manual';
    IF COL_LENGTH('dbo.response_evaluations', 'expected_behavior') IS NULL
      ALTER TABLE dbo.response_evaluations ADD expected_behavior NVARCHAR(MAX) NULL;
    IF COL_LENGTH('dbo.response_evaluations', 'true_label') IS NULL
      ALTER TABLE dbo.response_evaluations ADD true_label NVARCHAR(50) NULL;
    IF COL_LENGTH('dbo.response_evaluations', 'predicted_label') IS NULL
      ALTER TABLE dbo.response_evaluations ADD predicted_label NVARCHAR(50) NULL;
    IF COL_LENGTH('dbo.response_evaluations', 'review_notes') IS NULL
      ALTER TABLE dbo.response_evaluations ADD review_notes NVARCHAR(MAX) NULL;
    IF COL_LENGTH('dbo.response_evaluations', 'reviewed_by') IS NULL
      ALTER TABLE dbo.response_evaluations ADD reviewed_by NVARCHAR(100) NULL;
    IF COL_LENGTH('dbo.response_evaluations', 'reviewed_at') IS NULL
      ALTER TABLE dbo.response_evaluations ADD reviewed_at DATETIME2 NULL;
    IF COL_LENGTH('dbo.response_evaluations', 'created_at') IS NULL
      ALTER TABLE dbo.response_evaluations ADD created_at DATETIME2 NULL;
  `);

  // Ensure created_at is populated for old rows where column may have been added later.
  await pool.request().query(`
    UPDATE dbo.response_evaluations
    SET created_at = SYSUTCDATETIME()
    WHERE created_at IS NULL;
  `);

  // Legacy compatibility: older schema used system_response as required.
  await pool.request().query(`
    IF COL_LENGTH('dbo.response_evaluations', 'system_response') IS NOT NULL
    BEGIN
      UPDATE dbo.response_evaluations
      SET system_response = COALESCE(system_response, final_system_response, '')
      WHERE system_response IS NULL;
      BEGIN TRY
        ALTER TABLE dbo.response_evaluations ALTER COLUMN system_response NVARCHAR(MAX) NULL;
      END TRY
      BEGIN CATCH
        -- Keep running even if ALTER COLUMN fails due legacy constraints/indexes.
      END CATCH
    END
  `);
}

function normalizeDateRange(rangeRaw) {
  const range = String(rangeRaw || '60d').toLowerCase();
  if (['24h', '7d', '30d', '60d', 'year', 'ytd', 'all'].includes(range)) return range;
  return '60d';
}

function getDateRangeSqlCondition(range, fieldName) {
  switch (range) {
    case '24h':
      return `${fieldName} >= DATEADD(hour, -24, SYSUTCDATETIME())`;
    case '7d':
      return `${fieldName} >= DATEADD(day, -7, SYSUTCDATETIME())`;
    case '30d':
      return `${fieldName} >= DATEADD(day, -30, SYSUTCDATETIME())`;
    case '60d':
      return `${fieldName} >= DATEADD(day, -60, SYSUTCDATETIME())`;
    case 'year':
      return `${fieldName} >= DATEADD(day, -365, SYSUTCDATETIME())`;
    case 'ytd':
      return `${fieldName} >= DATEFROMPARTS(YEAR(GETUTCDATE()), 1, 1)`;
    default:
      return '';
  }
}

function getDateRangeKql(range) {
  switch (range) {
    case '24h': return '24h';
    case '7d': return '7d';
    case '30d': return '30d';
    case '60d': return '60d';
    case 'year': return '365d';
    case 'ytd': return '365d';
    default: return '60d';
  }
}

async function queryAppInsights(kql) {
  const workspaceId = (process.env.APPLICATIONINSIGHTS_WORKSPACE_ID || '').trim();
  if (!workspaceId) {
    return { rows: [], warning: 'APPLICATIONINSIGHTS_WORKSPACE_ID is not configured.' };
  }
  try {
    // Prefer local Azure CLI auth first to avoid repeated Managed Identity timeouts
    // when running on a developer machine.
    const credential = new ChainedTokenCredential(
      new AzureCliCredential(),
      new DefaultAzureCredential({
        excludeManagedIdentityCredential: true,
      })
    );
    const client = new LogsQueryClient(credential);
    const result = await client.queryWorkspace(workspaceId, kql);
    if (result.status !== 'Success') {
      const partial = result.partialError?.message || 'Partial query error.';
      logger.warn(`App Insights query partial failure: ${partial}`);
      return { rows: [], warning: partial };
    }
    const table = result.tables?.[0];
    if (!table) return { rows: [] };
    const rows = table.rows.map((row) => {
      const obj = {};
      table.columnDescriptors.forEach((col, idx) => {
        obj[col.name] = row[idx];
      });
      return obj;
    });
    return { rows };
  } catch (err) {
    logger.error(`App Insights query failed: ${err?.message || err}`);
    return { rows: [], warning: `Telemetry query unavailable: ${err?.message || err}` };
  }
}

async function withTimeout(promise, ms, label) {
  let timeoutId;
  const timeoutPromise = new Promise((_, reject) => {
    timeoutId = setTimeout(() => reject(new Error(`${label} timed out after ${ms}ms`)), ms);
  });
  try {
    return await Promise.race([promise, timeoutPromise]);
  } finally {
    clearTimeout(timeoutId);
  }
}

function dashboardPayloadFromMcp(username, data) {
  const amt = Number(data.outstanding_total_amount ?? 0);
  return {
    message: `Welcome ${username}!`,
    outstandingCount: Number(data.outstanding_quotes_count ?? 0),
    outstandingTotal: `$${amt.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`,
    unavailableItems: Number(data.out_of_stock_count ?? 0),
    totalQuotes: 0, // MCP endpoint does not expose grand total; default to 0
  };
}

async function fetchDashboardFromMcp() {
  const mcpApiKey = process.env.MCP_API_KEY || '';
  // Optional full URL when the MCP host does not use /quotes/admin/dashboard (e.g. backend/mcp
  // only exposes FastMCP under /mcp until you add HTTP routes on that service).
  const explicit = (process.env.MCP_DASHBOARD_METRICS_URL || '').trim();
  let url;
  if (explicit) {
    url = explicit;
  } else {
    const base = mcpQuotesApiBase();
    if (!base) {
      return null;
    }
    url = `${base}/quotes/admin/dashboard`;
  }
  const resp = await fetch(url, {
    headers: mcpApiKey ? { 'x-api-key': mcpApiKey } : {},
  });
  if (!resp.ok) {
    const txt = await resp.text();
    throw new Error(`MCP ${resp.status} ${txt}`);
  }
  return resp.json();
}

app.get('/admin/dashboard', authenticateToken, async (req, res) => {
  const username = req.user.username;
  const welcome = `Welcome ${username}!`;

  const sqlConfig = buildSqlConfig();
  if (sqlConfig) {
    try {
      const pool = await sql.connect(sqlConfig);
      // Single query: outstanding stats + grand total — avoids two round-trips
      const metrics = await pool.request().query(
        `SELECT
           SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END)                         AS outstanding_quotes_count,
           COALESCE(SUM(CASE WHEN status = 'active' THEN total_amount ELSE 0 END), 0)  AS outstanding_total_amount,
           COUNT(*)                                                                     AS total_quotes_count
         FROM Quotes`
      );
      // Count DISTINCT products customers actually requested (via active quotes)
      // that are currently out of stock — matches requirement:
      // "items requested by customers that are currently unavailable"
      const oos = await pool.request().query(
        `SELECT COUNT(DISTINCT qi.product_id) AS cnt
         FROM QuoteItems qi
         JOIN Inventory i ON qi.product_id = i.product_id
         JOIN Quotes q    ON qi.quote_id    = q.quote_id
         WHERE i.quantity_in_stock = 0
           AND q.status = 'active'`
      );
      return res.json({
        message: welcome,
        outstandingCount: metrics.recordset[0].outstanding_quotes_count,
        outstandingTotal: `$${Number(metrics.recordset[0].outstanding_total_amount).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`,
        unavailableItems: oos.recordset[0].cnt,
        totalQuotes: metrics.recordset[0].total_quotes_count,
      });
    } catch (err) {
      logger.warn(`Dashboard direct SQL failed, trying MCP: ${err.message}`);
    }
  } else {
    logger.info('Dashboard: Azure SQL env not fully set; using MCP if available.');
  }

  try {
    const mcpData = await fetchDashboardFromMcp();
    if (mcpData) {
      return res.json(dashboardPayloadFromMcp(username, mcpData));
    }
  } catch (err) {
    logger.error(`Dashboard MCP fallback failed: ${err.message}`);
  }

  return res.status(200).json({
    message: welcome,
    outstandingCount: 0,
    outstandingTotal: '$0.00',
    unavailableItems: 0,
    totalQuotes: 0,
    warning:
      'Live metrics unavailable. Set Azure SQL app settings on the admin app, or ensure MCP_BASE_URL reaches the quote API.',
  });
});

// Legacy business logs endpoint. This is business status data only, not response quality.
app.get('/admin/response-logs', authenticateToken, async (req, res) => {
  const sqlConfig = buildSqlConfig();

  // Graceful degradation: if Azure SQL env vars are not set, return empty logs with a
  // warning banner rather than a hard 503 — matches the /admin/dashboard pattern.
  if (!sqlConfig) {
    logger.info('[response-logs] Azure SQL not configured — returning empty log set with warning.');
    return res.json({
      success: true, logs: [], total: 0,
      warning: 'Live logs unavailable. Set AZURE_SQL_* environment variables to enable response log tracking.',
    });
  }

  // Parse and whitelist-validate filter query params
  const dateRange   = String(req.query.dateRange || 'all');
  const statusParam = String(req.query.status    || 'all');
  const validStatuses = ['active', 'ordered', 'expired', 'cancelled'];

  const conditions = [];

  // Date range — safe SQL date literals, no user text injected
  if      (dateRange === 'today') conditions.push(`CAST(q.created_at AS DATE) = CAST(SYSUTCDATETIME() AS DATE)`);
  else if (dateRange === 'week')  conditions.push(`q.created_at >= DATEADD(day, -7,  SYSUTCDATETIME())`);
  else if (dateRange === 'month') conditions.push(`q.created_at >= DATEADD(day, -30, SYSUTCDATETIME())`);

  // Status — whitelisted before interpolation
  const safeStatus = validStatuses.includes(statusParam.toLowerCase()) ? statusParam.toLowerCase() : null;
  if (safeStatus) conditions.push(`q.status = '${safeStatus}'`);

  const whereClause = conditions.length ? `WHERE ${conditions.join(' AND ')}` : '';

  try {
    const pool = await sql.connect(sqlConfig);

    // Total count matching current filter (drives the "Showing X of Y" UI counter)
    const countResult = await pool.request().query(`
      SELECT COUNT(*) AS total
      FROM Quotes q
      JOIN BusinessAccounts ba ON q.account_id = ba.account_id
      ${whereClause}
    `);
    const total = countResult.recordset[0].total;

    // Main data query — up to 200 rows
    const result = await pool.request().query(`
      SELECT TOP 200
        q.quote_id        AS id,
        q.created_at      AS timestamp,
        ba.email          AS email,
        ba.company_name   AS company,
        q.status          AS status,
        q.total_amount    AS total_amount
      FROM Quotes q
      JOIN BusinessAccounts ba ON q.account_id = ba.account_id
      ${whereClause}
      ORDER BY q.created_at DESC
    `);

    const logs = result.recordset.map(row => {
      const amt = Number(row.total_amount || 0);
      return {
        id: row.id,
        timestamp: row.quote_created_at || row.created_at || row.updated_at,
        email: row.email || 'unknown',
        company: row.company || 'Unknown',
        status: row.status || 'unknown',
        summary: `${row.company || 'Unknown company'} — Quote #${row.id} ($${amt.toLocaleString('en-US', { minimumFractionDigits: 2 })})`,
        response: `Quote ${row.status} — Total $${amt.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`,
      };
    });

    logger.info(`[response-logs] Served ${logs.length}/${total} records (dateRange=${dateRange}, status=${statusParam})`);
    return res.json({ success: true, logs, total });
  } catch (err) {
    logger.error(`[response-logs] SQL error: ${err.message}`);
    return res.json({
      success: true, logs: [], total: 0,
      warning: `Failed to load response logs: ${err.message}`,
    });
  }
});

app.get('/admin/response-evaluations', authenticateToken, async (req, res) => {
  const sqlConfig = buildSqlConfig();
  if (!sqlConfig) {
    return res.json({ success: true, evaluations: [], total: 0, warning: 'AZURE_SQL_* is not configured.' });
  }

  const range = normalizeDateRange(req.query.range);
  const classification = String(req.query.classification || '').trim();
  const customerEmail = String(req.query.customer_email || '').trim();

  try {
    const pool = await sql.connect(sqlConfig);
    await ensureResponseEvaluationsTable(pool);

    const conditions = [];
    const request = pool.request();

    const dateCondition = getDateRangeSqlCondition(range, 'quote_created_at');
    if (dateCondition) conditions.push(dateCondition);

    if (classification && classification.toLowerCase() !== 'all') {
      request.input('classification', sql.NVarChar(20), classification);
      conditions.push('classification = @classification');
    }
    if (customerEmail) {
      request.input('customerEmail', sql.NVarChar(255), `%${customerEmail}%`);
      conditions.push('customer_email LIKE @customerEmail');
    }

    const whereClause = conditions.length ? `WHERE ${conditions.join(' AND ')}` : '';
    const result = await request.query(`
      WITH Evals AS (
        SELECT
          re.id,
          el.id                                               AS response_log_id,
          el.customer_email,
          COALESCE(ba.company_name, 'Unknown')               AS company,
          COALESCE(re.customer_subject, 'Email Interaction') AS customer_subject,
          COALESCE(
            NULLIF(LTRIM(RTRIM(el.customer_email_content)), ''),
            re.customer_email_body,
            'No content'
          )                                                   AS customer_email_body,
          COALESCE(
            NULLIF(LTRIM(RTRIM(el.contoso_email_response)), ''),
            re.final_system_response,
            'No response recorded'
          )                                                   AS final_system_response,
          COALESCE(re.agent_name, 'userOrchestrator')        AS agent_name,
          COALESCE(re.classification, 'Pending')             AS classification,
          re.confidence_score,
          re.evaluator_source,
          re.review_notes,
          re.true_label,
          re.predicted_label,
          re.reviewed_by,
          re.reviewed_at,
          el.created_at                                       AS quote_created_at
        FROM EmailLogs el
        LEFT JOIN BusinessAccounts ba
          ON ba.email = el.customer_email
        LEFT JOIN dbo.response_evaluations re
          ON  re.customer_email = el.customer_email
          AND re.response_log_id = el.id
      )
      SELECT TOP 500 *
      FROM Evals
      ${whereClause}
      ORDER BY quote_created_at DESC
    `);
    const evaluations = result.recordset.map(row => ({
      ...row,
      timestamp: row.quote_created_at || row.created_at
    }));
    return res.json({ success: true, evaluations, total: result.recordset.length });
  } catch (err) {
    logger.error(`[response-evaluations] fetch failed: ${err?.message || err}`);
    return res.json({ success: true, evaluations: [], total: 0, warning: `Failed to load evaluations: ${err?.message || err}` });
  }
});

app.post('/admin/response-evaluations', authenticateToken, async (req, res) => {
  const sqlConfig = buildSqlConfig();
  if (!sqlConfig) return res.status(503).json({ success: false, error: 'AZURE_SQL_* is not configured.' });

  const body = req.body || {};
  if (!String(body.customer_email_body || '').trim() || !String(body.final_system_response || '').trim()) {
    return res.status(400).json({ success: false, error: 'customer_email_body and final_system_response are required.' });
  }

  try {
    const pool = await sql.connect(sqlConfig);
    await ensureResponseEvaluationsTable(pool);
    const request = pool.request()
      .input('response_log_id', sql.Int, body.response_log_id || null)
      .input('customer_email', sql.NVarChar(255), body.customer_email || null)
      .input('customer_subject', sql.NVarChar(500), body.customer_subject || null)
      .input('customer_email_body', sql.NVarChar(sql.MAX), body.customer_email_body)
      .input('final_system_response', sql.NVarChar(sql.MAX), body.final_system_response)
      .input('agent_name', sql.NVarChar(100), body.agent_name || null)
      .input('classification', sql.NVarChar(20), body.classification || null)
      .input('confidence_score', sql.Float, body.confidence_score ?? null)
      .input('evaluator_source', sql.NVarChar(50), body.evaluator_source || 'Manual')
      .input('expected_behavior', sql.NVarChar(sql.MAX), body.expected_behavior || null)
      .input('true_label', sql.NVarChar(50), body.true_label || null)
      .input('predicted_label', sql.NVarChar(50), body.predicted_label || null)
      .input('review_notes', sql.NVarChar(sql.MAX), body.review_notes || null)
      .input('reviewed_by', sql.NVarChar(100), body.reviewed_by || null);

    const result = await request.query(`
      IF COL_LENGTH('dbo.response_evaluations', 'system_response') IS NOT NULL
      BEGIN
        INSERT INTO dbo.response_evaluations (
          response_log_id, customer_email, customer_subject, customer_email_body,
          final_system_response, system_response, agent_name, classification, confidence_score,
          evaluator_source, expected_behavior, true_label, predicted_label,
          review_notes, reviewed_by, reviewed_at
        )
        OUTPUT INSERTED.*
        VALUES (
          @response_log_id, @customer_email, @customer_subject, @customer_email_body,
          @final_system_response, @final_system_response, @agent_name, @classification, @confidence_score,
          @evaluator_source, @expected_behavior, @true_label, @predicted_label,
          @review_notes, @reviewed_by,
          CASE WHEN @classification IS NULL OR @classification = '' THEN NULL ELSE SYSUTCDATETIME() END
        )
      END
      ELSE
      BEGIN
        INSERT INTO dbo.response_evaluations (
          response_log_id, customer_email, customer_subject, customer_email_body,
          final_system_response, agent_name, classification, confidence_score,
          evaluator_source, expected_behavior, true_label, predicted_label,
          review_notes, reviewed_by, reviewed_at
        )
        OUTPUT INSERTED.*
        VALUES (
          @response_log_id, @customer_email, @customer_subject, @customer_email_body,
          @final_system_response, @agent_name, @classification, @confidence_score,
          @evaluator_source, @expected_behavior, @true_label, @predicted_label,
          @review_notes, @reviewed_by,
          CASE WHEN @classification IS NULL OR @classification = '' THEN NULL ELSE SYSUTCDATETIME() END
        )
      END
    `);
    return res.status(201).json({ success: true, evaluation: result.recordset[0] });
  } catch (err) {
    logger.error(`[response-evaluations] create failed: ${err?.message || err}`);
    return res.status(500).json({ success: false, error: `Failed to create evaluation: ${err?.message || err}` });
  }
});

app.post('/admin/response-evaluations/seed-from-logs', authenticateToken, async (_req, res) => {
  const sqlConfig = buildSqlConfig();
  if (!sqlConfig) return res.status(503).json({ success: false, error: 'AZURE_SQL_* is not configured.' });
  try {
    const pool = await sql.connect(sqlConfig);
    await ensureResponseEvaluationsTable(pool);
    const result = await pool.request().query(`
      IF COL_LENGTH('dbo.response_evaluations', 'system_response') IS NOT NULL
      BEGIN
        INSERT INTO dbo.response_evaluations (
          response_log_id, customer_email, customer_subject, customer_email_body,
          final_system_response, system_response, agent_name, classification, confidence_score, evaluator_source
        )
        SELECT
          q.quote_id AS response_log_id,
          ba.email AS customer_email,
          CONCAT('Quote #', q.quote_id, ' request') AS customer_subject,
          CONCAT('Customer request from ', COALESCE(ba.company_name, 'unknown company')) AS customer_email_body,
          CONCAT('Legacy quote status: ', q.status, '; total: $', FORMAT(q.total_amount, 'N2')) AS final_system_response,
          CONCAT('Legacy quote status: ', q.status, '; total: $', FORMAT(q.total_amount, 'N2')) AS system_response,
          'userOrchestrator' AS agent_name,
          NULL AS classification,
          NULL AS confidence_score,
          'Manual' AS evaluator_source
        FROM Quotes q
        JOIN BusinessAccounts ba ON q.account_id = ba.account_id
        WHERE NOT EXISTS (
          SELECT 1 FROM dbo.response_evaluations re WHERE re.response_log_id = q.quote_id
        )
      END
      ELSE
      BEGIN
        INSERT INTO dbo.response_evaluations (
          response_log_id, customer_email, customer_subject, customer_email_body,
          final_system_response, agent_name, classification, confidence_score, evaluator_source
        )
        SELECT
          q.quote_id AS response_log_id,
          ba.email AS customer_email,
          CONCAT('Quote #', q.quote_id, ' request') AS customer_subject,
          CONCAT('Customer request from ', COALESCE(ba.company_name, 'unknown company')) AS customer_email_body,
          CONCAT('Legacy quote status: ', q.status, '; total: $', FORMAT(q.total_amount, 'N2')) AS final_system_response,
          'userOrchestrator' AS agent_name,
          NULL AS classification,
          NULL AS confidence_score,
          'Manual' AS evaluator_source
        FROM Quotes q
        JOIN BusinessAccounts ba ON q.account_id = ba.account_id
        WHERE NOT EXISTS (
          SELECT 1 FROM dbo.response_evaluations re WHERE re.response_log_id = q.quote_id
        )
      END
    `);
    return res.json({
      success: true,
      seeded_count: Number(result.rowsAffected?.[0] || 0),
      message: 'Seeded legacy business logs as pending manual reviews.'
    });
  } catch (err) {
    logger.error(`[response-evaluations] seed failed: ${err?.message || err}`);
    return res.status(500).json({ success: false, error: `Failed to seed from logs: ${err?.message || err}` });
  }
});

app.patch('/admin/response-evaluations/:id', authenticateToken, async (req, res) => {
  const sqlConfig = buildSqlConfig();
  if (!sqlConfig) return res.status(503).json({ success: false, error: 'AZURE_SQL_* is not configured.' });
  const id = Number(req.params.id);
  if (!Number.isFinite(id)) return res.status(400).json({ success: false, error: 'Invalid evaluation id.' });

  const body = req.body || {};
  try {
    const pool = await sql.connect(sqlConfig);
    await ensureResponseEvaluationsTable(pool);
    const request = pool.request()
      .input('id', sql.Int, id)
      .input('classification', sql.NVarChar(20), body.classification ?? null)
      .input('confidence_score', sql.Float, body.confidence_score ?? null)
      .input('review_notes', sql.NVarChar(sql.MAX), body.review_notes ?? null)
      .input('reviewed_by', sql.NVarChar(100), body.reviewed_by ?? null)
      .input('expected_behavior', sql.NVarChar(sql.MAX), body.expected_behavior ?? null)
      .input('true_label', sql.NVarChar(50), body.true_label ?? null)
      .input('predicted_label', sql.NVarChar(50), body.predicted_label ?? null);

    const result = await request.query(`
      UPDATE dbo.response_evaluations
      SET
        classification = @classification,
        confidence_score = @confidence_score,
        review_notes = @review_notes,
        reviewed_by = @reviewed_by,
        expected_behavior = @expected_behavior,
        true_label = @true_label,
        predicted_label = @predicted_label,
        reviewed_at = CASE
          WHEN @classification IS NULL OR @classification = '' THEN reviewed_at
          ELSE SYSUTCDATETIME()
        END
      OUTPUT INSERTED.*
      WHERE id = @id
    `);
    if (!result.recordset.length) return res.status(404).json({ success: false, error: 'Evaluation not found.' });
    return res.json({ success: true, evaluation: result.recordset[0] });
  } catch (err) {
    logger.error(`[response-evaluations] patch failed: ${err?.message || err}`);
    return res.status(500).json({ success: false, error: `Failed to update evaluation: ${err?.message || err}` });
  }
});

app.delete('/admin/clear-all-quotes', authenticateToken, async (req, res) => {
  const sqlConfig = buildSqlConfig();
  if (!sqlConfig) return res.status(503).json({ success: false, error: 'AZURE_SQL_* is not configured.' });
  try {
    const pool = await sql.connect(sqlConfig);
    await pool.request().query(`DELETE FROM dbo.response_evaluations`);
    await pool.request().query(`DELETE FROM QuoteItems`);
    const result = await pool.request().query(`DELETE FROM Quotes`);
    const deleted = result.rowsAffected?.[0] ?? 0;
    logger.info(`[clear-all-quotes] Deleted all quotes (${deleted} rows) by admin.`);
    return res.json({ success: true, deleted });
  } catch (err) {
    logger.error(`[clear-all-quotes] failed: ${err?.message || err}`);
    return res.status(500).json({ success: false, error: `Failed to clear quotes: ${err?.message || err}` });
  }
});

app.get('/admin/evaluation-summary', authenticateToken, async (req, res) => {
  const sqlConfig = buildSqlConfig();
  if (!sqlConfig) {
    return res.json({
      total_responses: 0, total_evaluated: 0, pending_review: 0,
      correct_count: 0, incorrect_count: 0, fallback_count: 0,
      accuracy_percent: 0, fallback_rate_percent: 0, average_confidence: null,
      warning: 'AZURE_SQL_* is not configured.'
    });
  }
  const range = normalizeDateRange(req.query.range);
  const where = getDateRangeSqlCondition(range, 'quote_created_at');
  const whereClause = where ? `WHERE ${where}` : '';
  try {
    const pool = await sql.connect(sqlConfig);
    await ensureResponseEvaluationsTable(pool);
    const result = await pool.request().query(`
      SELECT
        COUNT(*) AS total_responses,
        SUM(CASE WHEN re.classification IN ('Correct','Incorrect','Fallback') THEN 1 ELSE 0 END) AS total_evaluated,
        SUM(CASE WHEN re.classification IS NULL OR re.classification = 'Pending' THEN 1 ELSE 0 END) AS pending_review,
        SUM(CASE WHEN re.classification = 'Correct' THEN 1 ELSE 0 END) AS correct_count,
        SUM(CASE WHEN re.classification = 'Incorrect' THEN 1 ELSE 0 END) AS incorrect_count,
        SUM(CASE WHEN re.classification = 'Fallback' THEN 1 ELSE 0 END) AS fallback_count,
        AVG(CASE WHEN re.confidence_score IS NOT NULL THEN re.confidence_score END) AS average_confidence
      FROM EmailLogs el
      LEFT JOIN dbo.response_evaluations re
        ON  re.customer_email = el.customer_email
        AND re.response_log_id = el.id
      ${whereClause.replace('quote_created_at', 'el.created_at')}
    `);
    const r = result.recordset[0] || {};
    const totalEvaluated = Number(r.total_evaluated || 0);
    const correct = Number(r.correct_count || 0);
    const fallback = Number(r.fallback_count || 0);
    return res.json({
      total_responses: Number(r.total_responses || 0),
      total_evaluated: totalEvaluated,
      pending_review: Number(r.pending_review || 0),
      correct_count: correct,
      incorrect_count: Number(r.incorrect_count || 0),
      fallback_count: fallback,
      accuracy_percent: totalEvaluated ? (correct / totalEvaluated) * 100 : 0,
      fallback_rate_percent: totalEvaluated ? (fallback / totalEvaluated) * 100 : 0,
      average_confidence: r.average_confidence == null ? null : Number(r.average_confidence),
    });
  } catch (err) {
    logger.error(`[evaluation-summary] failed: ${err?.message || err}`);
    return res.status(500).json({ error: `Failed to load summary: ${err?.message || err}` });
  }
});

app.get('/admin/confusion-matrix', authenticateToken, async (req, res) => {
  const sqlConfig = buildSqlConfig();
  if (!sqlConfig) {
    return res.json({
      true_positives: 0, false_positives: 0, true_negatives: 0, false_negatives: 0,
      accuracy: 0, precision: 0, recall: 0, f1_score: 0,
      message: 'Confusion matrix requires test cases with expected labels.'
    });
  }
  const range = normalizeDateRange(req.query.range);
  const whereDate = getDateRangeSqlCondition(range, 'quote_created_at');
  const whereClause = whereDate ? `WHERE ${whereDate} AND true_label IS NOT NULL AND predicted_label IS NOT NULL` : `WHERE true_label IS NOT NULL AND predicted_label IS NOT NULL`;
  try {
    const pool = await sql.connect(sqlConfig);
    await ensureResponseEvaluationsTable(pool);
    const result = await pool.request().query(`
      SELECT
        SUM(CASE WHEN re.true_label = 'Correct' AND re.predicted_label = 'Correct' THEN 1 ELSE 0 END) AS tp,
        SUM(CASE WHEN re.true_label <> 'Correct' AND re.predicted_label = 'Correct' THEN 1 ELSE 0 END) AS fp,
        SUM(CASE WHEN re.true_label <> 'Correct' AND re.predicted_label <> 'Correct' THEN 1 ELSE 0 END) AS tn,
        SUM(CASE WHEN re.true_label = 'Correct' AND re.predicted_label <> 'Correct' THEN 1 ELSE 0 END) AS fn
      FROM dbo.response_evaluations re
      JOIN EmailLogs el
        ON  el.customer_email = re.customer_email
        AND el.id = re.response_log_id
      ${whereClause.replace('quote_created_at', 'el.created_at')}
    `);
    const row = result.recordset[0] || {};
    const tp = Number(row.tp || 0);
    const fp = Number(row.fp || 0);
    const tn = Number(row.tn || 0);
    const fn = Number(row.fn || 0);
    const total = tp + fp + tn + fn;
    const precisionDen = tp + fp;
    const recallDen = tp + fn;
    const precision = precisionDen ? tp / precisionDen : 0;
    const recall = recallDen ? tp / recallDen : 0;
    const f1 = (precision + recall) ? (2 * precision * recall) / (precision + recall) : 0;
    return res.json({
      true_positives: tp,
      false_positives: fp,
      true_negatives: tn,
      false_negatives: fn,
      accuracy: total ? (tp + tn) / total : 0,
      precision,
      recall,
      f1_score: f1,
      ...(total === 0 ? { message: 'Confusion matrix requires test cases with expected labels.' } : {})
    });
  } catch (err) {
    logger.error(`[confusion-matrix] failed: ${err?.message || err}`);
    return res.status(500).json({ error: `Failed to load confusion matrix: ${err?.message || err}` });
  }
});

app.get('/admin/agent-performance', authenticateToken, async (req, res) => {
  const range = normalizeDateRange(req.query.range);
  const lookback = getDateRangeKql(range);
  const kql = `
AppDependencies
| where TimeGenerated > ago(${lookback})
| where Name startswith "invoke_agent"
| extend agent = extract(@"invoke_agent\\s([a-zA-Z0-9_]+)", 1, Name)
| where agent in ("userOrchestrator", "email", "userQuote", "userPurchaseOrder", "userOnboarding")
| summarize calls = count(), errors = countif(Success == false), avgDurationSeconds = round(avg(DurationMs) / 1000, 2) by agent
| order by calls desc
`;
  const result = await queryAppInsights(kql);
  return res.json({ telemetry: result.rows, ...(result.warning ? { warning: result.warning } : {}) });
});

app.get('/admin/user-orchestrator-traces', authenticateToken, async (req, res) => {
  const range = normalizeDateRange(req.query.range);
  const lookback = getDateRangeKql(range);
  const kql = `
AppDependencies
| where TimeGenerated > ago(${lookback})
| where Name startswith "invoke_agent"
| where Name contains "userOrchestrator"
| project timestamp=TimeGenerated, operation_Id=OperationId, id=Id, name=Name, success=Success, duration=DurationMs, resultCode=ResultCode, data=Data, target=Target, customDimensions=Properties
| order by timestamp desc
| take 200
`;
  const result = await queryAppInsights(kql);
  return res.json({ traces: result.rows, ...(result.warning ? { warning: result.warning } : {}) });
});

app.get('/admin/agent-traces', authenticateToken, async (req, res) => {
  const range = normalizeDateRange(req.query.range);
  const lookback = getDateRangeKql(range);
  const kql = `
AppDependencies
| where TimeGenerated > ago(${lookback})
| where Name startswith "invoke_agent"
| extend agent = extract(@"invoke_agent\\s([a-zA-Z0-9_]+)", 1, Name)
| where agent in ("userOrchestrator", "email", "userQuote", "userPurchaseOrder", "userOnboarding")
| project timestamp=TimeGenerated, operation_Id=OperationId, id=Id, agent, name=Name, success=Success, duration=DurationMs, resultCode=ResultCode, data=Data, target=Target
| order by timestamp desc
| take 200
`;
  const result = await queryAppInsights(kql);
  return res.json({ traces: result.rows, ...(result.warning ? { warning: result.warning } : {}) });
});

app.get('/admin/trace-details/:operationId', authenticateToken, async (req, res) => {
  const operationId = String(req.params.operationId || '').trim();
  if (!operationId) return res.status(400).json({ error: 'operationId is required.' });
  const kql = `
let opId = "${operationId.replace(/"/g, '\\"')}";
union withsource=TableName isfuzzy=true AppDependencies, AppRequests, AppTraces, AppEvents, AppExceptions
| extend op = OperationId, ts = TimeGenerated, rowId = Id, n = Name, s = Success, d = DurationMs, rc = ResultCode, msg = Message, cd = Properties
| where op == opId
| extend agent = extract(@"invoke_agent\\s([a-zA-Z0-9_]+)", 1, n)
| project timestamp=ts, TableName, operation_Id=op, id=rowId, agent, name=n, success=s, duration=d, resultCode=rc, message=msg, customDimensions=cd
| order by timestamp asc
`;
  const result = await queryAppInsights(kql);
  return res.json({ rows: result.rows, ...(result.warning ? { warning: result.warning } : {}) });
});

// Temporary diagnostics endpoint to debug Log Analytics query behavior in this environment.
app.get('/admin/telemetry-debug', authenticateToken, async (_req, res) => {
  const workspaceId = (process.env.APPLICATIONINSIGHTS_WORKSPACE_ID || '').trim();
  if (!workspaceId) {
    return res.status(500).json({ success: false, error: 'APPLICATIONINSIGHTS_WORKSPACE_ID is not configured.' });
  }

  const tests = [
    {
      name: 'count_invoke_agent',
      query: "AppDependencies | where TimeGenerated > ago(60d) | where Name startswith 'invoke_agent' | summarize total=count()"
    },
    {
      name: 'user_orchestrator_sample',
      query: "AppDependencies | where TimeGenerated > ago(60d) | where Name startswith 'invoke_agent' | extend agent = extract(@'invoke_agent\\\\s([a-zA-Z0-9_]+)', 1, Name) | where agent == 'userOrchestrator' | project TimeGenerated, OperationId, Name, Success, DurationMs | order by TimeGenerated desc | take 5"
    }
  ];

  const credential = new ChainedTokenCredential(
    new AzureCliCredential(),
    new DefaultAzureCredential({
      excludeManagedIdentityCredential: true,
    })
  );
  const client = new LogsQueryClient(credential);
  const results = [];

  for (const test of tests) {
    try {
    logger.info(`[telemetry-debug] Running test: ${test.name}`);
    const result = await withTimeout(
      client.queryWorkspace(workspaceId, test.query),
      15000,
      `telemetry-debug ${test.name}`
    );
      results.push({
        name: test.name,
        status: result.status,
        rowCount: result.tables?.[0]?.rows?.length ?? 0,
        sampleRows: result.tables?.[0]?.rows?.slice(0, 5) ?? [],
        columns: result.tables?.[0]?.columnDescriptors?.map((c) => c.name) ?? [],
        partialError: result.partialError?.message || null,
      });
    } catch (err) {
      results.push({
        name: test.name,
        status: 'Error',
        error: err?.message || String(err),
      });
    }
  }

  return res.json({
    success: true,
    workspaceId,
    tests: results,
  });
});

// Unauthenticated local-only diagnostics helper.
app.get('/admin/telemetry-debug-open', async (_req, res) => {
  const baseQuery =
    "AppDependencies | where TimeGenerated > ago(60d) | where Name startswith 'invoke_agent' | summarize total=count()";
  const result = await queryAppInsights(baseQuery);
  return res.json({
    success: true,
    workspaceId: (process.env.APPLICATIONINSIGHTS_WORKSPACE_ID || '').trim(),
    query: baseQuery,
    rowCount: result.rows.length,
    rows: result.rows,
    warning: result.warning || null,
  });
});

// Simple Health Endpoint for Dashboard Status Bead
app.get('/admin/health', authenticateToken, (req, res) => {
  return res.json({ 
    status: 'ok', 
    timestamp: new Date().toISOString(),
    mcpBaseReached: process.env.MCP_BASE_URL ? true : false,
    appInsightsEnabled: process.env.APPLICATIONINSIGHTS_CONNECTION_STRING ? true : false
  });
});

// Tool-style admin commands endpoint (separate from the Foundry agent chat route)
app.post('/admin/chat/tools', authenticateToken, async (req, res) => {
  const { message } = req.body;
  logger.info(`Admin chat from ${req.user.username}: ${message}`);

  const lower = (message || '').toLowerCase();
  const quotesApiBase = mcpQuotesApiBase();
  const toolApiBase = process.env.TOOL_API_BASE_URL;
  const mcpApiKey = process.env.MCP_API_KEY || '';
  const toolApiKey = process.env.TOOL_API_KEY || process.env.MCP_API_KEY || '';

  try {
    // Help / capability prompt
    if (
      lower.includes('help') ||
      lower.includes('what can you do') ||
      lower.includes('commands')
    ) {
      return res.json({
        request_type: 'help',
        results: [
          { command: 'show outstanding quotes' },
          { command: 'show out of stock items' },
          { command: 'show dashboard metrics' },
          { command: 'show inventory' },
          { command: 'check inventory for SKU-1' },
          { command: 'show quote 1' }
        ]
      });
    }

    // Specific quote detail: "show quote 12"
    const quoteMatch = lower.match(/\bquote\s+(\d+)\b/);
    if (quoteMatch) {
      const quoteId = Number(quoteMatch[1]);

      const resp = await fetch(`${quotesApiBase}/quotes/admin/${quoteId}`, {
        headers: mcpApiKey ? { 'x-api-key': mcpApiKey } : {}
      });

      if (!resp.ok) {
        const txt = await resp.text();
        return res.status(502).json({
          request_type: 'quote_detail',
          error: `Quote detail failed: ${resp.status} ${txt}`,
          results: []
        });
      }

      const data = await resp.json();
      return res.json({
        request_type: 'quote_detail',
        results: [data]
      });
    }

    // Dashboard / summary
    if (
      lower.includes('dashboard') ||
      lower.includes('summary') ||
      lower.includes('metrics') ||
      lower.includes('overview')
    ) {
      const resp = await fetch(`${quotesApiBase}/quotes/admin/dashboard`, {
        headers: mcpApiKey ? { 'x-api-key': mcpApiKey } : {}
      });

      if (!resp.ok) {
        const txt = await resp.text();
        return res.status(502).json({
          request_type: 'dashboard_metrics',
          error: `Dashboard metrics failed: ${resp.status} ${txt}`,
          results: []
        });
      }

      const data = await resp.json();
      return res.json({
        request_type: 'dashboard_metrics',
        results: [data]
      });
    }

    // Outstanding quotes
    if (lower.includes('quote') || lower.includes('outstanding')) {
      const resp = await fetch(`${quotesApiBase}/quotes/admin/outstanding`, {
        headers: mcpApiKey ? { 'x-api-key': mcpApiKey } : {}
      });

      if (!resp.ok) {
        const txt = await resp.text();
        return res.status(502).json({
          request_type: 'outstanding_quotes',
          error: `Outstanding quotes failed: ${resp.status} ${txt}`,
          results: []
        });
      }

      const data = await resp.json();
      return res.json({
        request_type: 'outstanding_quotes',
        results: data
      });
    }

    // Out of stock
    if (
      lower.includes('out of stock') ||
      lower.includes('unavailable') ||
      lower.includes('oos')
    ) {
      const resp = await fetch(`${quotesApiBase}/quotes/admin/out-of-stock`, {
        headers: mcpApiKey ? { 'x-api-key': mcpApiKey } : {}
      });

      if (!resp.ok) {
        const txt = await resp.text();
        return res.status(502).json({
          request_type: 'out_of_stock',
          error: `Out-of-stock failed: ${resp.status} ${txt}`,
          results: []
        });
      }

      const data = await resp.json();
      return res.json({
        request_type: 'out_of_stock',
        results: data
      });
    }

    // Full inventory list
    if (lower.includes('inventory')) {
      const resp = await fetch(`${quotesApiBase}/quotes/admin/inventory`, {
        headers: mcpApiKey ? { 'x-api-key': mcpApiKey } : {}
      });

      if (!resp.ok) {
        const txt = await resp.text();
        return res.status(502).json({
          request_type: 'inventory_list',
          error: `Inventory list failed: ${resp.status} ${txt}`,
          results: []
        });
      }

      const data = await resp.json();
      return res.json({
        request_type: 'inventory_list',
        results: data
      });
    }

    // Inventory by SKU from tool API, e.g. "check inventory for SKU-1"
    const skuMatch = message?.match(/\bSKU[-\s]?\d+\b/i);
    if (skuMatch) {
      // Guard: TOOL_API_BASE_URL must be set or we'd build a URL like "undefined/inventory/..."
      if (!toolApiBase) {
        return res.status(503).json({
          request_type: 'inventory_item',
          error: 'TOOL_API_BASE_URL is not configured on this server. Cannot look up individual SKUs.',
          results: []
        });
      }

      const sku = skuMatch[0].replace(/\s+/g, '-').toUpperCase();

      const resp = await fetch(`${toolApiBase}/inventory/get_item/${encodeURIComponent(sku)}`, {
        headers: toolApiKey ? { 'x-api-key': toolApiKey } : {}
      });

      if (!resp.ok) {
        const txt = await resp.text();
        return res.status(502).json({
          request_type: 'inventory_item',
          error: `Inventory item failed: ${resp.status} ${txt}`,
          results: []
        });
      }

      const data = await resp.json();
      return res.json({
        request_type: 'inventory_item',
        results: [data]
      });
    }

    return res.json({
      request_type: 'unknown',
      results: [],
      message: 'Try asking about dashboard metrics, outstanding quotes, out-of-stock items, inventory, or a specific quote ID.'
    });
  } catch (err) {
    logger.error(`Admin chat error: ${err?.message || err}`);
    return res.status(500).json({
      request_type: 'error',
      results: [],
      error: 'Failed to process admin chat request.'
    });
  }
});

// Debug info endpoint — returns server/env state; only accessible when authenticated
app.get('/admin/debug/info', authenticateToken, (req, res) => {
  const mem = process.memoryUsage();
  res.json({
    node: process.version,
    platform: `${process.platform}/${process.arch}`,
    pid: process.pid,
    uptimeSec: Math.floor(process.uptime()),
    memory: {
      rss:       `${(mem.rss       / 1024 / 1024).toFixed(1)} MB`,
      heapUsed:  `${(mem.heapUsed  / 1024 / 1024).toFixed(1)} MB`,
      heapTotal: `${(mem.heapTotal / 1024 / 1024).toFixed(1)} MB`,
    },
    env: {
      JWT_SECRET:       process.env.JWT_SECRET       ? '✓ set'    : '✗ MISSING',
      PROJECT_ENDPOINT: process.env.PROJECT_ENDPOINT || '✗ MISSING',
      AGENT_NAME:       process.env.AGENT_NAME       || '✗ MISSING',
      MCP_BASE_URL:     process.env.MCP_BASE_URL     || '✗ MISSING',
      MCP_DASHBOARD_METRICS_URL: process.env.MCP_DASHBOARD_METRICS_URL || '— not set (defaults to …/quotes/admin/dashboard)',
      mcpQuotesApiBase: mcpQuotesApiBase() || '✗ MISSING (used for /quotes/... calls)',
      MCP_API_KEY:      process.env.MCP_API_KEY      ? '✓ set'    : '— not set',
      TOOL_API_BASE_URL:process.env.TOOL_API_BASE_URL|| '— not set',
      TOOL_API_KEY:     process.env.TOOL_API_KEY     ? '✓ set'    : '— not set',
      AZURE_SQL_SERVER: process.env.AZURE_SQL_SERVER ? '✓ set'    : '✗ MISSING',
      AZURE_SQL_DATABASE: process.env.AZURE_SQL_DATABASE ? '✓ set' : '✗ MISSING',
      AZURE_SQL_USERNAME: process.env.AZURE_SQL_USERNAME ? '✓ set' : '✗ MISSING',
      AZURE_SQL_PASSWORD: process.env.AZURE_SQL_PASSWORD ? '✓ set' : '✗ MISSING',
    },
    timestamp: new Date().toISOString(),
  });
});

// Catch-all for frontend routing
app.get('/{*any}', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

const server = app.listen(PORT, () => {
  logger.info(`Server running on http://localhost:${PORT}`);
  logger.info(`[startup] Node.js ${process.version} | PID ${process.pid} | PORT ${PORT}`);
  logger.info(
    `[startup] Config: ` +
    `JWT_SECRET=${process.env.JWT_SECRET ? 'SET' : 'MISSING'} | ` +
    `PROJECT_ENDPOINT=${process.env.PROJECT_ENDPOINT || 'MISSING'} | ` +
    `AGENT_NAME=${process.env.AGENT_NAME || 'MISSING'} | ` +
    `MCP_BASE_URL=${process.env.MCP_BASE_URL || 'MISSING'} | ` +
    `MCP_API_KEY=${process.env.MCP_API_KEY ? 'SET' : 'not set'} | ` +
    `TOOL_API_BASE_URL=${process.env.TOOL_API_BASE_URL || 'not set'} | ` +
    `AZURE_SQL=${buildSqlConfig() ? 'SET' : 'not set (dashboard uses MCP fallback)'}`
  );
  console.log('PID:', process.pid);
  console.log('server listening:', server.listening);
});

server.on('close', () => {
  console.log('SERVER CLOSE EVENT FIRED');
});

process.on('exit', (code) => {
  console.log('PROCESS EXIT EVENT. code =', code);
});

process.on('beforeExit', (code) => {
  console.log('PROCESS BEFOREEXIT EVENT. code =', code);
});

process.on('uncaughtException', (err) => {
  console.error('UNCAUGHT EXCEPTION:', err);
});

process.on('unhandledRejection', (err) => {
  console.error('UNHANDLED REJECTION:', err);
});
