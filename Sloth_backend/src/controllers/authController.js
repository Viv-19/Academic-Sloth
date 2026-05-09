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

        // Send back success response
        res.status(201).json({
            status: 'success',
            message: 'User registered successfully!',
            data: result
        });

    } catch (error) {
        // If the service threw an error (e.g. "User already exists")
        if (error.message === 'User with this email already exists.') {
            return res.status(409).json({ status: 'error', message: error.message });
        }
        // Otherwise, pass to the global error handler
        next(error);
    }
}

/**
 * Handle POST /auth/login
 */
async function login(req, res, next) {
    try {
        const { email, password } = req.body;

        // Basic validation
        if (!email || !password) {
            return res.status(400).json({ status: 'error', message: 'Email and password are required.' });
        }

        // Call the service to verify credentials
        const result = await authService.loginUser(email, password);

        // Send back success response
        res.status(200).json({
            status: 'success',
            message: 'Logged in successfully!',
            data: result
        });

    } catch (error) {
        // Handle invalid credentials specifically
        if (error.message === 'Invalid email or password.') {
            return res.status(401).json({ status: 'error', message: error.message });
        }
        // Otherwise, pass to global error handler
        next(error);
    }
}

module.exports = {
    signup,
    login
};
