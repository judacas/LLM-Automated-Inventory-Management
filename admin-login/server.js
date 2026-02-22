// server.js
const express = require('express');
const cookieParser = require('cookie-parser');
const jwt = require('jsonwebtoken');
const path = require('path');
const logger = require('./utils/logger');

const app = express();
const PORT = 3000;
const JWT_SECRET = 'your_jwt_secret_here'; // in production, move to .env

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

// Logout
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

// Protected dashboard data endpoint
app.get('/admin/dashboard', authenticateToken, (req, res) => {
  logger.info(`Dashboard data accessed by: ${req.user.username}`);
  res.json({
    message: `Welcome ${req.user.username}!`,
    outstandingCount: 5,
    outstandingTotal: '$1200',
    unavailableItems: 2
  });
});

// ===== Admin Chat Loop (Demo / Sponsor-ready) =====
app.post('/admin/chat', authenticateToken, async (req, res) => {
  const { message } = req.body;
  logger.info(`Admin chat from ${req.user.username}: ${message}`);

  const lower = (message || '').toLowerCase();

  // Demo: simulate Foundry agent classification JSON
  let out = { request_type: 'unknown', results: [] };

  if (lower.includes('help') || lower.includes('what can you do')) {
    out.request_type = 'help';
  } else if (lower.includes('unavailable') || lower.includes('out of stock')) {
    out.request_type = 'unavailable_items';
  } else if (lower.includes('quote') || lower.includes('outstanding')) {
    out.request_type = 'outstanding_quotes';
  }

  // Demo: backend "intercepts" request_type and fills mock results
  // (Later replace these with DB MCP queries)
  if (out.request_type === 'outstanding_quotes') {
    out.results = [
      { quote_id: 'Q-1002', total: 418.50 },
      { quote_id: 'Q-1011', total: 92.00 }
    ];
  } else if (out.request_type === 'unavailable_items') {
    out.results = [
      { sku: 'SKU-009', requested_qty: 4, available_qty: 0 }
    ];
  } else if (out.request_type === 'help') {
    out.results = [];
  }

  return res.json(out);
});

// Catch-all for frontend routing
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.listen(PORT, () => {
  logger.info(`Server running on http://localhost:${PORT}`);
});
