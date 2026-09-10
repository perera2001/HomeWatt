# WattWise AI Backend

Node.js and Express backend for WattWise AI, a multi-agent electricity usage planner for Sri Lankan homes.

This backend currently supports authentication, protected user routes, protected admin routes, MySQL storage for registered users, and a clean placeholder route for future Python AI-service integration.

## Tech Stack

- Node.js
- Express.js
- MySQL
- mysql2
- bcryptjs
- jsonwebtoken
- dotenv
- cors
- nodemon

## Folder Structure

```text
src/
  app.js                         Express app, middleware, route mounting
  server.js                      Server startup and database connectivity check
  config/
    db.js                        MySQL connection pool
    env.js                       Environment variable loading and validation
  modules/
    auth/                        Register, login, current-user auth, JWT middleware
    users/                       Protected normal user routes
    admin/                       Protected admin routes
    ai/                          Placeholder for future AI service integration
  middleware/
    error.middleware.js          404 and centralized error responses
  utils/
    apiError.js                  Reusable HTTP error class
sql/
  schema.sql                     MySQL database and users table SQL
```

## Install Dependencies

```bash
npm install
```

Or install packages manually:

```bash
npm install express mysql2 bcryptjs jsonwebtoken dotenv cors
npm install --save-dev nodemon
```

## Environment Setup

Create a `.env` file in the backend root by copying `.env.example`:

```env
PORT=5000
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_NAME=wattwise_ai
JWT_SECRET=replace_with_secure_secret
JWT_EXPIRES_IN=1d
ADMIN_NAME=System Admin
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=admin_password_here
```

Do not commit the real `.env` file. The admin password is read from environment variables and is not hardcoded in source code.

## MySQL Database Setup

Run this in MySQL Workbench:

```sql
CREATE DATABASE IF NOT EXISTS wattwise_ai;

USE wattwise_ai;

CREATE TABLE IF NOT EXISTS users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  email VARCHAR(150) NOT NULL UNIQUE,
  password VARCHAR(255) NOT NULL,
  role ENUM('user', 'admin') DEFAULT 'user',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

The same SQL is available in `sql/schema.sql`.

## Run the Backend

Development:

```bash
npm run dev
```

Production-style start:

```bash
npm start
```

Base URL:

```text
http://localhost:5000
```

Health check:

```text
GET http://localhost:5000/api/health
```

## Postman Tests

### Register User

```text
POST http://localhost:5000/api/auth/register
Content-Type: application/json
```

```json
{
  "name": "Nandun",
  "email": "nandun@example.com",
  "password": "password123"
}
```

Example response:

```json
{
  "message": "Registration successful",
  "user": {
    "id": 1,
    "name": "Nandun",
    "email": "nandun@example.com",
    "role": "user"
  }
}
```

Registration creates the account only. Use the login endpoint to generate a JWT token for authenticated requests.

### Login User

```text
POST http://localhost:5000/api/auth/login
Content-Type: application/json
```

```json
{
  "email": "nandun@example.com",
  "password": "password123"
}
```

Example response:

```json
{
  "message": "Login successful",
  "token": "...",
  "user": {
    "id": 1,
    "name": "Nandun",
    "email": "nandun@example.com",
    "role": "user"
  }
}
```

### Login Admin

Use the admin credentials from your `.env`.

```text
POST http://localhost:5000/api/auth/login
Content-Type: application/json
```

```json
{
  "email": "admin@example.com",
  "password": "admin_password_here"
}
```

Example response:

```json
{
  "message": "Admin login successful",
  "token": "...",
  "user": {
    "id": null,
    "name": "System Admin",
    "email": "admin@example.com",
    "role": "admin"
  }
}
```

### Get Current User

Works for both user and admin tokens.

```text
GET http://localhost:5000/api/auth/me
Authorization: Bearer YOUR_TOKEN
```

### User Home

Requires a user token.

```text
GET http://localhost:5000/api/users/home
Authorization: Bearer USER_TOKEN
```

Response:

```json
{
  "message": "Welcome to user home page"
}
```

### Admin Home

Requires an admin token.

```text
GET http://localhost:5000/api/admin/home
Authorization: Bearer ADMIN_TOKEN
```

Response:

```json
{
  "message": "Welcome to admin home page"
}
```

### Admin List Users

Requires an admin token.

```text
GET http://localhost:5000/api/admin/users
Authorization: Bearer ADMIN_TOKEN
```

Response:

```json
{
  "users": [
    {
      "id": 1,
      "name": "Nandun",
      "email": "nandun@example.com",
      "role": "user",
      "created_at": "2026-09-09T05:15:00.000Z"
    }
  ]
}
```

### AI Placeholder Chat

Requires any valid authenticated token.

```text
POST http://localhost:5000/api/ai/chat
Authorization: Bearer YOUR_TOKEN
Content-Type: application/json
```

```json
{
  "message": "How can I reduce electricity usage?"
}
```

Response:

```json
{
  "message": "AI service connection will be implemented later"
}
```

## Authorization Rules

- Public users can register only as `user`.
- Admin login is controlled by `ADMIN_EMAIL`, `ADMIN_PASSWORD`, and `ADMIN_NAME` from `.env`.
- User JWTs can access `/api/users/home`.
- Admin JWTs can access `/api/admin/home` and `/api/admin/users`.
- User JWTs cannot access admin routes.
- `/api/auth/me` accepts both user and admin JWTs.
- `/api/ai/chat` accepts any valid authenticated JWT.

## Notes

- No frontend is implemented in this backend.
- No Python AI-service connection is implemented yet.
- The AI module is intentionally separated so future internal service calls can be added cleanly in `src/modules/ai/ai.service.js`.
