const express = require('express');
const userController = require('./user.controller');
const { authenticate, authorizeRoles } = require('../auth/auth.middleware');

const router = express.Router();

router.get('/home', authenticate, authorizeRoles('user'), userController.home);

module.exports = router;
