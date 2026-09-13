const pool = require('../../config/db');
const ApiError = require('../../utils/apiError');
const aiService = require('../ai/ai.service');

let planSnapshotColumnReady = false;

const parseSessionId = (sessionId) => {
  const parsedId = Number(sessionId);

  if (!Number.isInteger(parsedId) || parsedId <= 0) {
    throw new ApiError(400, 'Session ID must be a positive integer');
  }

  return parsedId;
};

const createTitle = (message) => {
  if (message.length <= 50) {
    return message;
  }

  return `${message.slice(0, 47)}...`;
};

const ensurePlanSnapshotColumn = async () => {
  if (planSnapshotColumnReady) {
    return;
  }

  try {
    await pool.execute(
      'ALTER TABLE chat_sessions ADD COLUMN plan_snapshot JSON NULL'
    );
  } catch (error) {
    if (error.code !== 'ER_DUP_FIELDNAME') {
      throw error;
    }
  }

  planSnapshotColumnReady = true;
};

const getPlanSnapshot = async (userId, sessionId) => {
  await ensurePlanSnapshotColumn();

  const [rows] = await pool.execute(
    'SELECT plan_snapshot FROM chat_sessions WHERE id = ? AND user_id = ? LIMIT 1',
    [sessionId, userId]
  );
  const snapshot = rows[0]?.plan_snapshot;

  if (!snapshot) {
    return null;
  }

  if (typeof snapshot === 'string') {
    try {
      return JSON.parse(snapshot);
    } catch (error) {
      return null;
    }
  }

  return snapshot;
};

const savePlanSnapshot = async (userId, sessionId, planSnapshot) => {
  if (!planSnapshot) {
    return;
  }

  await ensurePlanSnapshotColumn();
  await pool.execute(
    'UPDATE chat_sessions SET plan_snapshot = ? WHERE id = ? AND user_id = ?',
    [JSON.stringify(planSnapshot), sessionId, userId]
  );
};

const saveUserMessage = async (userId, sessionId, message) => {
  const connection = await pool.getConnection();

  try {
    await connection.beginTransaction();

    let activeSessionId;

    if (sessionId === undefined || sessionId === null) {
      const [result] = await connection.execute(
        'INSERT INTO chat_sessions (user_id, title) VALUES (?, ?)',
        [userId, createTitle(message)]
      );
      activeSessionId = result.insertId;
    } else {
      activeSessionId = parseSessionId(sessionId);
      const [sessions] = await connection.execute(
        'SELECT id FROM chat_sessions WHERE id = ? AND user_id = ? LIMIT 1 FOR UPDATE',
        [activeSessionId, userId]
      );

      if (!sessions[0]) {
        throw new ApiError(404, 'Chat session not found');
      }
    }

    await connection.execute(
      'INSERT INTO chat_messages (session_id, user_id, role, content) VALUES (?, ?, ?, ?)',
      [activeSessionId, userId, 'user', message]
    );

    await connection.execute(
      'UPDATE chat_sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?',
      [activeSessionId]
    );

    await connection.commit();
    return activeSessionId;
  } catch (error) {
    await connection.rollback();
    throw error;
  } finally {
    connection.release();
  }
};

const saveAssistantMessage = async (userId, sessionId, answer) => {
  const connection = await pool.getConnection();

  try {
    await connection.beginTransaction();
    await connection.execute(
      'INSERT INTO chat_messages (session_id, user_id, role, content) VALUES (?, ?, ?, ?)',
      [sessionId, userId, 'assistant', answer]
    );
    await connection.execute(
      'UPDATE chat_sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?',
      [sessionId, userId]
    );
    await connection.commit();
  } catch (error) {
    await connection.rollback();
    throw error;
  } finally {
    connection.release();
  }
};

const createChatResponse = async (
  userId,
  {
    session_id: sessionId,
    message,
    year,
    month,
    max_budget_lkr: maxBudgetLkr,
    appliances
  } = {}
) => {
  if (typeof message !== 'string' || !message.trim()) {
    throw new ApiError(400, 'Message is required and cannot be empty');
  }

  const cleanMessage = message.trim();
  const activeSessionId = await saveUserMessage(userId, sessionId, cleanMessage);
  const previousPlan = await getPlanSnapshot(userId, activeSessionId);
  const aiResponse = await aiService.sendChatMessageToAiService({
    userId,
    sessionId: activeSessionId,
    message: cleanMessage,
    year,
    month,
    maxBudgetLkr,
    appliances,
    previousPlan
  });
  const assistantResponse = aiResponse.answer;

  await saveAssistantMessage(userId, activeSessionId, assistantResponse);
  await savePlanSnapshot(userId, activeSessionId, aiResponse.planSnapshot);

  return {
    session_id: activeSessionId,
    user_message: cleanMessage,
    assistant_response: assistantResponse
  };
};

const getSessions = async (userId) => {
  const [rows] = await pool.execute(
    `SELECT id, title, created_at, updated_at
     FROM chat_sessions
     WHERE user_id = ?
     ORDER BY updated_at DESC, id DESC`,
    [userId]
  );

  return rows;
};

const getSession = async (userId, sessionId) => {
  const validSessionId = parseSessionId(sessionId);
  const [sessions] = await pool.execute(
    `SELECT id, title, created_at, updated_at
     FROM chat_sessions
     WHERE id = ? AND user_id = ?
     LIMIT 1`,
    [validSessionId, userId]
  );

  const session = sessions[0];

  if (!session) {
    throw new ApiError(404, 'Chat session not found');
  }

  const [messages] = await pool.execute(
    `SELECT id, role, content, created_at
     FROM chat_messages
     WHERE session_id = ? AND user_id = ?
     ORDER BY created_at ASC, id ASC`,
    [validSessionId, userId]
  );

  return {
    ...session,
    messages
  };
};

const deleteSession = async (userId, sessionId) => {
  const validSessionId = parseSessionId(sessionId);
  const [result] = await pool.execute(
    'DELETE FROM chat_sessions WHERE id = ? AND user_id = ?',
    [validSessionId, userId]
  );

  if (result.affectedRows === 0) {
    throw new ApiError(404, 'Chat session not found');
  }
};

module.exports = {
  createChatResponse,
  getSessions,
  getSession,
  deleteSession
};
