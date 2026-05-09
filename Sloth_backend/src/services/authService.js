const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const prisma = require('../config/db');
const emailService = require('./emailService'); // Import our new email service!

const JWT_SECRET = process.env.JWT_SECRET || 'fallback_secret_for_dev';

/**
 * Registers a new user and sends an OTP for verification.
 * Note: We don't log them in yet! They must verify the OTP first.
 */
async function registerUser(name, email, password) {
    const existingUser = await prisma.user.findUnique({
        where: { email }
    });

    if (existingUser) {
        throw new Error('User with this email already exists.');
    }

    const salt = await bcrypt.genSalt(10);
    const hashedPassword = await bcrypt.hash(password, salt);

    // Generate a 6-digit OTP and set expiry to 10 minutes from now
    const otp = emailService.generateOTP();
    const otpExpiry = new Date(Date.now() + 10 * 60 * 1000); 

    // Create user in database (is_verified defaults to false)
    await prisma.user.create({
        data: {
            name,
            email,
            password_hash: hashedPassword,
            otp: otp,
            otp_expiry: otpExpiry
        }
    });

    // Send the OTP via email using HTML formatting
    const htmlBody = emailService.getHtmlTemplate(
        'Verify your Email',
        `Welcome ${name}! We're excited to have you join Academic Sloth. Please use the verification code below to complete your registration.`,
        otp
    );

    await emailService.sendEmail(
        email, 
        'Verify your Academic Sloth Account', 
        `Welcome ${name}! Your verification code is: ${otp}. This code expires in 10 minutes.`,
        htmlBody
    );

    return { message: 'OTP sent to email. Please verify.' };
}

/**
 * Verifies the OTP sent during signup or password reset
 */
async function verifyOtp(email, otp) {
    const user = await prisma.user.findUnique({ where: { email } });

    if (!user) {
        throw new Error('User not found.');
    }

    if (user.is_verified && user.otp !== otp) {
         // Minor safety check: if they are already verified, we don't want them re-verifying randomly
         // But we will allow this function to be used for both "Signup Verification" and "Forgot Password verification"
    }

    // Check if OTP matches and hasn't expired
    if (user.otp !== otp) {
        throw new Error('Invalid OTP.');
    }

    if (new Date() > user.otp_expiry) {
        throw new Error('OTP has expired. Please request a new one.');
    }

    // If we reach here, the OTP is correct and valid!
    // Update the user to be verified, and clear out the OTP fields so they can't be reused.
    await prisma.user.update({
        where: { email },
        data: {
            is_verified: true,
            otp: null,
            otp_expiry: null
        }
    });

    // Generate JWT Token (because they successfully verified, we can log them in directly)
    const token = jwt.sign({ userId: user.id }, JWT_SECRET, { expiresIn: '7d' });

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

/**
 * Logs in an existing user
 */
async function loginUser(email, password) {
    const user = await prisma.user.findUnique({ where: { email } });

    if (!user) {
        throw new Error('Invalid email or password.');
    }

    // NEW CHECK: Prevent login if email is not verified
    if (!user.is_verified) {
        throw new Error('Please verify your email before logging in.');
    }

    const isMatch = await bcrypt.compare(password, user.password_hash);
    if (!isMatch) {
        throw new Error('Invalid email or password.');
    }

    const token = jwt.sign({ userId: user.id }, JWT_SECRET, { expiresIn: '7d' });

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

/**
 * Initiates the Forgot Password flow by sending an OTP
 */
async function forgotPassword(email) {
    const user = await prisma.user.findUnique({ where: { email } });

    if (!user) {
        throw new Error('User not found.');
    }

    // Generate new OTP and expiry
    const otp = emailService.generateOTP();
    const otpExpiry = new Date(Date.now() + 10 * 60 * 1000); 

    // Save to database
    await prisma.user.update({
        where: { email },
        data: {
            otp: otp,
            otp_expiry: otpExpiry
        }
    });

    // Send the email using HTML formatting
    const htmlBody = emailService.getHtmlTemplate(
        'Password Reset',
        'You requested a password reset for your Academic Sloth account. Please use the code below to create a new password. If you did not request this, please ignore this email.',
        otp
    );

    await emailService.sendEmail(
        email, 
        'Password Reset - Academic Sloth', 
        `You requested a password reset. Your OTP code is: ${otp}. This code expires in 10 minutes.`,
        htmlBody
    );

    return { message: 'Password reset OTP sent to email.' };
}

/**
 * Resets the password using an OTP
 */
async function resetPassword(email, otp, newPassword) {
    const user = await prisma.user.findUnique({ where: { email } });

    if (!user) {
        throw new Error('User not found.');
    }

    // Verify OTP
    if (user.otp !== otp) {
        throw new Error('Invalid OTP.');
    }

    if (new Date() > user.otp_expiry) {
        throw new Error('OTP has expired. Please request a new one.');
    }

    // Hash the new password
    const salt = await bcrypt.genSalt(10);
    const hashedPassword = await bcrypt.hash(newPassword, salt);

    // Save new password and clear OTP
    await prisma.user.update({
        where: { email },
        data: {
            password_hash: hashedPassword,
            otp: null,
            otp_expiry: null
        }
    });

    return { message: 'Password has been successfully reset. You can now log in.' };
}

module.exports = {
    registerUser,
    verifyOtp,
    loginUser,
    forgotPassword,
    resetPassword
};
