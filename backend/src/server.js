const app = require('./app');
const env = require('./config/env');
const pool = require('./config/db');

const startServer = async () => {
  try {
    await pool.query('SELECT 1');

    app.listen(env.port, () => {
      console.log(`WattWise AI backend running on port ${env.port}`);
    });
  } catch (error) {
    console.error('Failed to start server:', error.message);
    process.exit(1);
  }
};

startServer();
