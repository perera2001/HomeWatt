# WattWise AI Backend

Node.js and Express backend for WattWise AI, a multi-agent electricity usage planner for Sri Lankan homes.

This backend currently supports authentication, protected user routes, protected admin routes, MySQL storage for registered users, user-owned chat sessions and history, and clean placeholders for future Python AI-service integration.

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
    chat/                        User chat sessions and message history
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

CREATE TABLE IF NOT EXISTS chat_sessions (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  title VARCHAR(255) NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS chat_messages (
  id INT AUTO_INCREMENT PRIMARY KEY,
  session_id INT NOT NULL,
  user_id INT NOT NULL,
  role ENUM('user', 'assistant') NOT NULL,
  content TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
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

### Create a New Chat Session

Requires a user token. The first message becomes the session title, shortened to a maximum of 50 characters.

```text
POST http://localhost:5000/api/chat
Authorization: Bearer USER_TOKEN
Content-Type: application/json
```

```json
{
  "message": "I have TV 100W, iron 1000W and water motor 750W. My budget is Rs. 3000 for September 2026."
}
```

Example response:

```json
{
  "message": "Chat response created successfully",
  "session_id": 1,
  "user_message": "I have TV 100W, iron 1000W and water motor 750W. My budget is Rs. 3000 for September 2026.",
  "assistant_response": "AI service connection will be implemented later."
}
```

### Continue an Existing Chat Session

Use a `session_id` returned by the new-chat request. The session must belong to the logged-in user.

```text
POST http://localhost:5000/api/chat
Authorization: Bearer USER_TOKEN
Content-Type: application/json
```

```json
{
  "session_id": 1,
  "message": "Can you reduce TV usage more?"
}
```

Example response:

```json
{
  "message": "Chat response created successfully",
  "session_id": 1,
  "user_message": "Can you reduce TV usage more?",
  "assistant_response": "AI service connection will be implemented later."
}
```

### List Chat Sessions

Returns only the logged-in user's sessions, with the most recently updated first.

```text
GET http://localhost:5000/api/chat/sessions
Authorization: Bearer USER_TOKEN
```

Example response:

```json
{
  "message": "Chat sessions fetched successfully",
  "sessions": [
    {
      "id": 1,
      "title": "I have TV 100W, iron 1000W and water motor...",
      "created_at": "2026-09-10T06:00:00.000Z",
      "updated_at": "2026-09-10T06:05:00.000Z"
    }
  ]
}
```

### Get One Chat Session

Returns the session and its messages only when it belongs to the logged-in user.

```text
GET http://localhost:5000/api/chat/sessions/1
Authorization: Bearer USER_TOKEN
```

Example response:

```json
{
  "message": "Chat session fetched successfully",
  "session": {
    "id": 1,
    "title": "I have TV 100W, iron 1000W and water motor...",
    "created_at": "2026-09-10T06:00:00.000Z",
    "updated_at": "2026-09-10T06:05:00.000Z",
    "messages": [
      {
        "id": 1,
        "role": "user",
        "content": "I have TV 100W, iron 1000W and water motor 750W. My budget is Rs. 3000 for September 2026.",
        "created_at": "2026-09-10T06:00:00.000Z"
      },
      {
        "id": 2,
        "role": "assistant",
        "content": "AI service connection will be implemented later.",
        "created_at": "2026-09-10T06:00:00.000Z"
      }
    ]
  }
}
```

### Delete a Chat Session

Deletes the logged-in user's session. Its messages are removed by `ON DELETE CASCADE`.

```text
DELETE http://localhost:5000/api/chat/sessions/1
Authorization: Bearer USER_TOKEN
```

Example response:

```json
{
  "message": "Chat session deleted successfully"
}
```

## Chat Test Flow

1. Run `sql/schema.sql` in MySQL Workbench to create the two chat tables.
2. Start the backend with `npm run dev`.
3. Register a normal user, then log in to receive a user JWT.
4. Add `Authorization: Bearer USER_TOKEN` to every chat request.
5. Create a chat with `POST /api/chat` without `session_id`.
6. Continue it with another `POST /api/chat` using the returned `session_id`.
7. List sessions, fetch the session history, and then delete it.
8. Try the same session ID with another user's token; the API returns `404 Chat session not found`.

## Authorization Rules

- Public users can register only as `user`.
- Admin login is controlled by `ADMIN_EMAIL`, `ADMIN_PASSWORD`, and `ADMIN_NAME` from `.env`.
- User JWTs can access `/api/users/home`.
- Admin JWTs can access `/api/admin/home` and `/api/admin/users`.
- User JWTs cannot access admin routes.
- `/api/auth/me` accepts both user and admin JWTs.
- `/api/ai/chat` accepts any valid authenticated JWT.
- `/api/chat` routes accept normal user JWTs and only expose sessions owned by that user.

## Notes

- No frontend is implemented in this backend.
- No Python AI-service connection is implemented yet.
- The AI module is intentionally separated so future internal service calls can be added cleanly in `src/modules/ai/ai.service.js`.
