const express = require('express');
const adminController = require('./admin.controller');
const { authenticate, authorizeRoles } = require('../auth/auth.middleware');

const router = express.Router();

router.get('/home', authenticate, authorizeRoles('admin'), adminController.home);
router.get('/users', authenticate, authorizeRoles('admin'), adminController.getUsers);

module.exports = router;
