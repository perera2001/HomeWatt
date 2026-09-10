const axios = require('axios');
const env = require('../../config/env');
const ApiError = require('../../utils/apiError');

const chatPlaceholder = () => {
  return {
    message: 'AI service connection will be implemented later'
  };
};

const sendChatMessageToAiService = async ({ userId, sessionId, message }) => {
  const baseUrl = env.aiService.url.replace(/\/+$/, '');
  const headers = {};

  if (env.aiService.internalToken) {
    headers['X-Internal-Token'] = env.aiService.internalToken;
  }

  try {
    const response = await axios.post(
      `${baseUrl}/chat`,
      {
        user_id: userId,
        session_id: sessionId,
        message
      },
      {
        headers,
        timeout: 10000
      }
    );

    if (typeof response.data?.answer !== 'string' || !response.data.answer.trim()) {
      throw new ApiError(502, 'AI service returned an invalid response');
    }

    return response.data.answer.trim();
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }

    if (axios.isAxiosError(error) && !error.response) {
      throw new ApiError(503, 'AI service is currently unavailable');
    }

    throw new ApiError(502, 'AI service request failed');
  }
};

module.exports = {
  chatPlaceholder,
  sendChatMessageToAiService
};
