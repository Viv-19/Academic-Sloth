const authService = require('../services/authService');

/**
 * Handle POST /auth/signup
 */
async function signup(req, res, next) {
    try {
        const { name, email, password } = req.body;

        // Basic validation
        if (!name || !email || !password) {
            return res.status(400).json({ status: 'error', message: 'Name, email, and password are required.' });
        }

        // Call the service to do the hard work
        const result = await authService.registerUser(name, email, password);

        // Send back success response (Note: no token here yet, they must verify!)
        res.status(201).json({
            status: 'success',
            message: result.message // "OTP sent to email. Please verify."
        });

    } catch (error) {
        if (error.message === 'User with this email already exists.') {
            return res.status(409).json({ status: 'error', message: error.message });
        }
        next(error);
    }
}

/**
 * Handle POST /auth/verify-otp
 */
async function verifyOtp(req, res, next) {
    try {
        const { email, otp } = req.body;

        if (!email || !otp) {
            return res.status(400).json({ status: 'error', message: 'Email and OTP are required.' });
        }

        // Call the service to verify the OTP. If successful, it returns the user & token!
        const result = await authService.verifyOtp(email, otp);

        res.status(200).json({
            status: 'success',
            message: 'Email verified successfully! You are now logged in.',
            data: result
        });

    } catch (error) {
        // Handle common OTP errors
        if (error.message === 'Invalid OTP.' || error.message === 'OTP has expired. Please request a new one.' || error.message === 'User not found.') {
            return res.status(400).json({ status: 'error', message: error.message });
        }
        next(error);
    }
}

/**
 * Handle POST /auth/login
 */
async function login(req, res, next) {
    try {
        const { email, password } = req.body;

        if (!email || !password) {
            return res.status(400).json({ status: 'error', message: 'Email and password are required.' });
        }

        const result = await authService.loginUser(email, password);

        res.status(200).json({
            status: 'success',
            message: 'Logged in successfully!',
            data: result
        });

    } catch (error) {
        if (error.message === 'Invalid email or password.' || error.message === 'Please verify your email before logging in.') {
            return res.status(401).json({ status: 'error', message: error.message });
        }
        next(error);
    }
}

/**
 * Handle POST /auth/forgot-password
 */
async function forgotPassword(req, res, next) {
    try {
        const { email } = req.body;

        if (!email) {
            return res.status(400).json({ status: 'error', message: 'Email is required.' });
        }

        const result = await authService.forgotPassword(email);

        res.status(200).json({
            status: 'success',
            message: result.message
        });

    } catch (error) {
        if (error.message === 'User not found.') {
            return res.status(404).json({ status: 'error', message: error.message });
        }
        next(error);
    }
}

/**
 * Handle POST /auth/reset-password
 */
async function resetPassword(req, res, next) {
    try {
        const { email, otp, newPassword } = req.body;

        if (!email || !otp || !newPassword) {
            return res.status(400).json({ status: 'error', message: 'Email, OTP, and new password are required.' });
        }

        const result = await authService.resetPassword(email, otp, newPassword);

        res.status(200).json({
            status: 'success',
            message: result.message
        });

    } catch (error) {
        if (error.message === 'Invalid OTP.' || error.message === 'OTP has expired. Please request a new one.' || error.message === 'User not found.') {
            return res.status(400).json({ status: 'error', message: error.message });
        }
        next(error);
    }
}

module.exports = {
    signup,
    verifyOtp,
    login,
    forgotPassword,
    resetPassword
};
