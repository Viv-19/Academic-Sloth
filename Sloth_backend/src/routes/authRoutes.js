const express = require('express');
const authController = require('../controllers/authController');

const router = express.Router();

// Define routes and map them to controller functions
router.post('/signup', authController.signup);
router.post('/verify-otp', authController.verifyOtp); // NEW
router.post('/login', authController.login);
router.post('/forgot-password', authController.forgotPassword); // NEW
router.post('/reset-password', authController.resetPassword); // NEW

module.exports = router;
