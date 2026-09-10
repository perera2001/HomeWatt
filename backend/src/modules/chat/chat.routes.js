const express = require('express');
const chatController = require('./chat.controller');
const { authenticate, authorizeRoles } = require('../auth/auth.middleware');

const router = express.Router();

router.use(authenticate, authorizeRoles('user'));

router.post('/', chatController.createChatResponse);
router.get('/sessions', chatController.getSessions);
router.get('/sessions/:id', chatController.getSession);
router.delete('/sessions/:id', chatController.deleteSession);

module.exports = router;
