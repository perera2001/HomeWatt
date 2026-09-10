const chatService = require('./chat.service');

const createChatResponse = async (req, res, next) => {
  try {
    const result = await chatService.createChatResponse(req.user.id, req.body);

    res.status(201).json({
      message: 'Chat response created successfully',
      ...result
    });
  } catch (error) {
    next(error);
  }
};

const getSessions = async (req, res, next) => {
  try {
    const sessions = await chatService.getSessions(req.user.id);

    res.status(200).json({
      message: 'Chat sessions fetched successfully',
      sessions
    });
  } catch (error) {
    next(error);
  }
};

const getSession = async (req, res, next) => {
  try {
    const session = await chatService.getSession(req.user.id, req.params.id);

    res.status(200).json({
      message: 'Chat session fetched successfully',
      session
    });
  } catch (error) {
    next(error);
  }
};

const deleteSession = async (req, res, next) => {
  try {
    await chatService.deleteSession(req.user.id, req.params.id);

    res.status(200).json({
      message: 'Chat session deleted successfully'
    });
  } catch (error) {
    next(error);
  }
};

module.exports = {
  createChatResponse,
  getSessions,
  getSession,
  deleteSession
};
