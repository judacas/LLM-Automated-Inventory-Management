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
const logger = require('./utils/logger');

const app = express();
const PORT = process.env.PORT || 3000;
const JWT_SECRET = process.env.JWT_SECRET;
const MCP_BASE_URL = process.env.MCP_BASE_URL;
const MCP_API_KEY = process.env.MCP_API_KEY;

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

    // Create one conversation per logged-in browser session
    if (!conversationId) {
      const conversation = await createConversation();
      conversationId = conversation.id;

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

    if (!extracted) {
      const summary = summarizeFoundryResponse(response);
      logger.warn(`[${requestId}] Foundry returned empty text output (${durationMs}ms): ${JSON.stringify(summary)}`);
      return res.json({
        success: true,
        empty: true,
        reply: '',
        requestId,
      });
    }

    logger.info(`[${requestId}] Admin chat success (${durationMs}ms, chars=${extracted.length})`);
    return res.json({
      success: true,
      reply: extracted,
      requestId,
    });
  } catch (err) {
    const durationMs = Date.now() - startedAt;
    const errMsg = String(err?.message || err);
    logger.error(`[${requestId}] Admin chat error (${durationMs}ms): ${err?.stack || errMsg}`);

    // If the agent requested MCP tool approval, we want a clear, non-scary message.
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
const sql = require('mssql');

const sqlConfig = {
  user: process.env.AZURE_SQL_USERNAME,
  password: process.env.AZURE_SQL_PASSWORD,
  database: process.env.AZURE_SQL_DATABASE,
  server: process.env.AZURE_SQL_SERVER,
  options: { encrypt: true, trustServerCertificate: false }
};

app.get('/admin/dashboard', authenticateToken, async (req, res) => {
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
      message: `Welcome ${req.user.username}!`,
      outstandingCount: metrics.recordset[0].outstanding_quotes_count,
      outstandingTotal: `$${Number(metrics.recordset[0].outstanding_total_amount).toFixed(2)}`,
      unavailableItems: oos.recordset[0].cnt
    });
  } catch (err) {
    logger.error(`Dashboard DB error: ${err.message}`);
    return res.status(500).json({ outstandingCount: 0, outstandingTotal: '$0.00', unavailableItems: 0 });
  }
});

// Tool-style admin commands endpoint (separate from the Foundry agent chat route)
app.post('/admin/chat/tools', authenticateToken, async (req, res) => {
  const { message } = req.body;
  logger.info(`Admin chat from ${req.user.username}: ${message}`);

  const lower = (message || '').toLowerCase();
  const mcpBase = process.env.MCP_BASE_URL;
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

      const resp = await fetch(`${mcpBase}/quotes/admin/${quoteId}`, {
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
      const resp = await fetch(`${mcpBase}/quotes/admin/dashboard`, {
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
      const resp = await fetch(`${mcpBase}/quotes/admin/outstanding`, {
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
      const resp = await fetch(`${mcpBase}/quotes/admin/out-of-stock`, {
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
      const resp = await fetch(`${mcpBase}/quotes/admin/inventory`, {
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

// Catch-all for frontend routing
app.get('/{*any}', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

const server = app.listen(PORT, () => {
  logger.info(`Server running on http://localhost:${PORT}`);
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
