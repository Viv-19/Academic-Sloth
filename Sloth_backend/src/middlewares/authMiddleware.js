const jwt = require('jsonwebtoken');

const JWT_SECRET = process.env.JWT_SECRET || 'fallback_secret_for_dev';

/**
 * Middleware to protect routes that require authentication.
 * It checks for a valid JWT token in the Authorization header.
 */
function protect(req, res, next) {
    // 1. Get the token from the header
    const authHeader = req.headers.authorization;

    if (!authHeader || !authHeader.startsWith('Bearer ')) {
        return res.status(401).json({ status: 'error', message: 'Not authorized. No token provided.' });
    }

    const token = authHeader.split(' ')[1];

    try {
        // 2. Verify the token
        const decoded = jwt.verify(token, JWT_SECRET);

        // 3. Attach the user ID to the request object so the next route can use it
        req.user = { id: decoded.userId };
        
        // 4. Move to the next middleware or controller
        next();
    } catch (error) {
        return res.status(401).json({ status: 'error', message: 'Not authorized. Invalid or expired token.' });
    }
}

module.exports = {
    protect
};
