const express = require('express');
const authController = require('../controllers/authController');

const router = express.Router();

// Define routes and map them to controller functions
router.post('/signup', authController.signup);
router.post('/login', authController.login);

module.exports = router;
