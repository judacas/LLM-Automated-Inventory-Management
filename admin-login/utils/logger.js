//Admin Sign-In Logs To Track Login Attempts

const { createLogger, format, transports } = require('winston');
const path = require('path');

const logger = createLogger({
  level: 'info',
  format: format.combine(
    format.timestamp({ format: 'YYYY-MM-DD HH:mm:ss' }),
    format.printf(
      info => `[${info.timestamp}] ${info.level.toUpperCase()}: ${info.message}`
    )
  ),
  transports: [
    new transports.Console(), // shows logs in terminal
    new transports.File({
      filename: path.join(__dirname, '../logs/server.log'),
      level: 'info',
      maxsize: 5 * 1024 * 1024, // 5MB max per file
      maxFiles: 5,               // keep last 5 logs
      tailable: true
    })
  ]
});

module.exports = logger;
