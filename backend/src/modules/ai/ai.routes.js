const express = require('express');
const aiController = require('./ai.controller');
const { authenticate } = require('../auth/auth.middleware');

const router = express.Router();

router.post('/chat', authenticate, aiController.chat);

module.exports = router;
