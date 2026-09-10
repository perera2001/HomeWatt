const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const pool = require('../../config/db');
const env = require('../../config/env');
const ApiError = require('../../utils/apiError');

const createToken = (user) => {
  return jwt.sign(
    {
      id: user.id,
      name: user.name,
      email: user.email,
      role: user.role
    },
    env.jwt.secret,
    { expiresIn: env.jwt.expiresIn }
  );
};

const sanitizeUser = (user) => ({
  id: user.id,
  name: user.name,
  email: user.email,
  role: user.role
});

const findUserByEmail = async (email) => {
  const [rows] = await pool.execute(
    'SELECT id, name, email, password, role, created_at FROM users WHERE email = ? LIMIT 1',
    [email]
  );

  return rows[0];
};

const findUserById = async (id) => {
  const [rows] = await pool.execute(
    'SELECT id, name, email, role, created_at FROM users WHERE id = ? LIMIT 1',
    [id]
  );

  return rows[0];
};

const register = async ({ name, email, password }) => {
  if (!name || !email || !password) {
    throw new ApiError(400, 'Name, email, and password are required');
  }

  if (password.length < 8) {
    throw new ApiError(400, 'Password must be at least 8 characters');
  }

  const normalizedEmail = email.trim().toLowerCase();
  const existingUser = await findUserByEmail(normalizedEmail);

  if (existingUser) {
    throw new ApiError(409, 'Email is already registered');
  }

  const hashedPassword = await bcrypt.hash(password, 10);

  const [result] = await pool.execute(
    'INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)',
    [name.trim(), normalizedEmail, hashedPassword, 'user']
  );

  const user = {
    id: result.insertId,
    name: name.trim(),
    email: normalizedEmail,
    role: 'user'
  };

  return {
    user: sanitizeUser(user)
  };
};

const login = async ({ email, password }) => {
  if (!email || !password) {
    throw new ApiError(400, 'Email and password are required');
  }

  const normalizedEmail = email.trim().toLowerCase();
  const adminEmail = env.admin.email.trim().toLowerCase();

  if (normalizedEmail === adminEmail && password === env.admin.password) {
    const adminUser = {
      id: null,
      name: env.admin.name,
      email: env.admin.email,
      role: 'admin'
    };

    return {
      message: 'Admin login successful',
      token: createToken(adminUser),
      user: adminUser
    };
  }

  const user = await findUserByEmail(normalizedEmail);

  if (!user) {
    throw new ApiError(401, 'Invalid email or password');
  }

  const isPasswordValid = await bcrypt.compare(password, user.password);

  if (!isPasswordValid) {
    throw new ApiError(401, 'Invalid email or password');
  }

  const cleanUser = sanitizeUser(user);

  return {
    message: 'Login successful',
    token: createToken(cleanUser),
    user: cleanUser
  };
};

const getCurrentUser = async (authUser) => {
  if (authUser.role === 'admin') {
    return {
      id: null,
      name: env.admin.name,
      email: env.admin.email,
      role: 'admin'
    };
  }

  const user = await findUserById(authUser.id);

  if (!user) {
    throw new ApiError(404, 'User not found');
  }

  return user;
};

module.exports = {
  register,
  login,
  getCurrentUser
};
