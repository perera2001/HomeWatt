const axios = require('axios');
const env = require('../../config/env');
const ApiError = require('../../utils/apiError');

const chatPlaceholder = () => {
  return {
    message: 'AI service connection will be implemented later'
  };
};

const formatAiServiceError = (data) => {
  if (!data) {
    return 'AI service request failed';
  }

  if (typeof data.detail === 'string') {
    return `AI service request failed: ${data.detail}`;
  }

  if (Array.isArray(data.detail)) {
    const details = data.detail
      .map((item) => item?.msg || item?.message)
      .filter(Boolean)
      .join(', ');

    if (details) {
      return `AI service request failed: ${details}`;
    }
  }

  if (typeof data.message === 'string') {
    return `AI service request failed: ${data.message}`;
  }

  return 'AI service request failed';
};

const sendChatMessageToAiService = async ({
  userId,
  sessionId,
  message,
  year,
  month,
  maxBudgetLkr,
  appliances,
  previousPlan
}) => {
  const baseUrl = env.aiService.url.replace(/\/+$/, '');
  const headers = {};

  if (env.aiService.internalToken) {
    headers.Authorization = `Bearer ${env.aiService.internalToken}`;
  }

  try {
    const response = await axios.post(
      `${baseUrl}/chat`,
      {
        user_id: userId,
        session_id: sessionId,
        message,
        year,
        month,
        max_budget_lkr: maxBudgetLkr,
        appliances,
        previous_plan: previousPlan || null,
        include_plan_snapshot: true
      },
      {
        headers,
        timeout: 10000
      }
    );

    if (typeof response.data?.answer !== 'string' || !response.data.answer.trim()) {
      throw new ApiError(502, 'AI service returned an invalid response');
    }

    return {
      answer: response.data.answer.trim(),
      planSnapshot: response.data.plan_snapshot || null
    };
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }

    if (axios.isAxiosError(error) && !error.response) {
      throw new ApiError(503, 'AI service is currently unavailable');
    }

    if (axios.isAxiosError(error) && error.response) {
      throw new ApiError(502, formatAiServiceError(error.response.data));
    }

    throw new ApiError(502, 'AI service request failed');
  }
};

module.exports = {
  chatPlaceholder,
  sendChatMessageToAiService
};
