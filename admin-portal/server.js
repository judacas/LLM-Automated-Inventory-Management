// server.js
require('dotenv').config();

const express = require('express');
const cookieParser = require('cookie-parser');
const jwt = require('jsonwebtoken');
const path = require('path');
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

// Logout8
app.post('/auth/logout', (req, res) => {
  res.clearCookie('token');
  logger.info('User logged out');
  res.json({ success: true });
});

// Protect dashboard.html itself (prevents direct access without cookie)
app.get('/dashboard.html', authenticateToken, (req, res) => {
  logger.info(`dashboard.html served to: ${req.user.username}`);
  res.sendFile(path.join(__dirname, 'public', 'dashboard.html'));
});

app.get('/admin/dashboard', authenticateToken, async (req, res) => {
  try {
    logger.info(`Dashboard data accessed by: ${req.user.username}`);

    const mcpBase = process.env.MCP_BASE_URL;
    const apiKey = process.env.MCP_API_KEY || '';

    const metricsResp = await fetch(`${mcpBase}/quotes/admin/dashboard`, {
      headers: apiKey ? { 'x-api-key': apiKey } : {}
    });

    if (!metricsResp.ok) {
      const txt = await metricsResp.text();
      return res.status(502).json({ error: `MCP dashboard failed: ${metricsResp.status} ${txt}` });
    }

    const metrics = await metricsResp.json();

    const outResp = await fetch(`${mcpBase}/quotes/admin/out-of-stock`, {
      headers: apiKey ? { 'x-api-key': apiKey } : {}
    });

    if (!outResp.ok) {
      const txt = await outResp.text();
      return res.status(502).json({ error: `MCP out-of-stock failed: ${outResp.status} ${txt}` });
    }

    const out = await outResp.json();
    const unavailableItems = Array.isArray(out) ? out.length : 0;

    return res.json({
      message: `Welcome ${req.user.username}!`,
      outstandingCount: metrics.outstanding_quotes_count ?? 0,
      outstandingTotal: `$${Number(metrics.outstanding_total_amount ?? 0).toFixed(2)}`,
      unavailableItems
    });
  } catch (err) {
    logger.error(`Dashboard fetch error: ${err?.message || err}`);
    return res.status(500).json({
      message: `Welcome ${req.user.username}!`,
      outstandingCount: 0,
      outstandingTotal: '$0.00',
      unavailableItems: 0
    });
  }
});

app.post('/admin/chat', authenticateToken, async (req, res) => {
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
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.listen(PORT, () => {
  logger.info(`Server running on http://localhost:${PORT}`);
});
