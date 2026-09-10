const pool = require('../../config/db');

const getHomeMessage = () => {
  return 'Welcome to admin home page';
};

const getAllUsers = async () => {
  const [rows] = await pool.execute(
    'SELECT id, name, email, role, created_at FROM users ORDER BY created_at DESC'
  );

  return rows;
};

module.exports = {
  getHomeMessage,
  getAllUsers
};
