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

// Protected dashboard
app.get('/admin/dashboard', authenticateToken, (req, res) => {
  logger.info(`Dashboard accessed by: ${req.user.username}`);
  res.json({
    message: `Welcome back, ${req.user.username}!`,
    outstandingCount: 5,
    outstandingTotal: `$${1200}`,
    unavailableItems: 2
  });
});

// Catch-all for frontend routing
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.listen(PORT, () => {
  logger.info(`Server running on http://localhost:${PORT}`);
});
