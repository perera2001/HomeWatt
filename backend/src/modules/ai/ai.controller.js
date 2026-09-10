const aiService = require('./ai.service');

const chat = (req, res) => {
  res.status(200).json(aiService.chatPlaceholder());
};

module.exports = {
  chat
};
