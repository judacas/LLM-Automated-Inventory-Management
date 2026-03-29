// server.js
require('dotenv').config();

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

function dashboardPayloadFromMcp(username, data) {
  const amt = Number(data.outstanding_total_amount ?? 0);
  return {
    message: `Welcome ${username}!`,
    outstandingCount: Number(data.outstanding_quotes_count ?? 0),
    outstandingTotal: `$${amt.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`,
    unavailableItems: Number(data.out_of_stock_count ?? 0),
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
      const metrics = await pool.request().query(
        `SELECT COUNT(*) AS outstanding_quotes_count,
                COALESCE(SUM(total_amount), 0) AS outstanding_total_amount
         FROM Quotes WHERE status = 'active'`
      );
      const oos = await pool.request().query(
        `SELECT COUNT(*) AS cnt FROM Inventory WHERE quantity_in_stock = 0`
      );
      return res.json({
        message: welcome,
        outstandingCount: metrics.recordset[0].outstanding_quotes_count,
        outstandingTotal: `$${Number(metrics.recordset[0].outstanding_total_amount).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`,
        unavailableItems: oos.recordset[0].cnt,
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
    warning:
      'Live metrics unavailable. Set Azure SQL app settings on the admin app, or ensure MCP_BASE_URL reaches the quote API.',
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
