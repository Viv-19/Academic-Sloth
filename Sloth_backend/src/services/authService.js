const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const prisma = require('../config/db');

// Read the secret key from the environment variables
const JWT_SECRET = process.env.JWT_SECRET || 'fallback_secret_for_dev';

/**
 * Registers a new user
 * @param {string} name 
 * @param {string} email 
 * @param {string} password 
 * @returns Object containing user info and token
 */
async function registerUser(name, email, password) {
    // 1. Check if user already exists
    const existingUser = await prisma.user.findUnique({
        where: { email }
    });

    if (existingUser) {
        throw new Error('User with this email already exists.');
    }

    // 2. Hash the password
    const salt = await bcrypt.genSalt(10);
    const hashedPassword = await bcrypt.hash(password, salt);

    // 3. Create user in database
    const newUser = await prisma.user.create({
        data: {
            name,
            email,
            password_hash: hashedPassword
        }
    });

    // 4. Generate JWT Token
    const token = jwt.sign({ userId: newUser.id }, JWT_SECRET, { expiresIn: '7d' });

    // 5. Return user (excluding password) and token
    return {
        user: {
            id: newUser.id,
            name: newUser.name,
            email: newUser.email,
            subscription_tier: newUser.subscription_tier
        },
        token
    };
}

/**
 * Logs in an existing user
 * @param {string} email 
 * @param {string} password 
 * @returns Object containing user info and token
 */
async function loginUser(email, password) {
    // 1. Find user by email
    const user = await prisma.user.findUnique({
        where: { email }
    });

    if (!user) {
        throw new Error('Invalid email or password.');
    }

    // 2. Compare passwords
    const isMatch = await bcrypt.compare(password, user.password_hash);
    if (!isMatch) {
        throw new Error('Invalid email or password.');
    }

    // 3. Generate JWT Token
    const token = jwt.sign({ userId: user.id }, JWT_SECRET, { expiresIn: '7d' });

    // 4. Return user info and token
    return {
        user: {
            id: user.id,
            name: user.name,
            email: user.email,
            subscription_tier: user.subscription_tier
        },
        token
    };
}

module.exports = {
    registerUser,
    loginUser
};
