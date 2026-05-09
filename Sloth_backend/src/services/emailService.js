const nodemailer = require('nodemailer');

/**
 * Creates a "transporter" object.
 * Think of the transporter as our digital mail carrier. We configure it
 * with our email provider's settings (in this case, Gmail) and our credentials.
 */
const transporter = nodemailer.createTransport({
    service: 'gmail', // Nodemailer has built-in support for Gmail
    auth: {
        user: process.env.EMAIL_USER, // Your Gmail address from .env
        pass: process.env.EMAIL_PASS  // Your 16-character App Password from .env
    }
});

/**
 * Generates a beautiful HTML email template matching the Academic Sloth theme.
 * @param {string} title - The title of the email
 * @param {string} body - The main content
 * @param {string} otp - The 6-digit OTP code to highlight
 * @returns {string} The full HTML string
 */
function getHtmlTemplate(title, body, otp) {
    return `
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body { font-family: 'Arial', sans-serif; background-color: #f8f7f6; margin: 0; padding: 0; }
            .container { max-width: 600px; margin: 40px auto; background-color: #221910; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }
            .header { background-color: #ec7f13; padding: 30px; text-align: center; }
            .header h1 { color: #221910; margin: 0; font-size: 28px; }
            .content { padding: 40px 30px; color: #ffffff; text-align: center; }
            .content p { font-size: 16px; line-height: 1.6; margin-bottom: 25px; color: #e0e0e0; }
            .otp-box { background-color: rgba(255,255,255,0.05); border: 2px dashed #ec7f13; border-radius: 8px; padding: 20px; margin: 30px 0; }
            .otp-code { font-size: 36px; font-weight: bold; letter-spacing: 8px; color: #ec7f13; margin: 0; }
            .footer { padding: 20px; text-align: center; font-size: 12px; color: #888888; border-top: 1px solid rgba(255,255,255,0.1); }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Academic Sloth</h1>
            </div>
            <div class="content">
                <h2 style="color: #ffffff; margin-top: 0;">${title}</h2>
                <p>${body}</p>
                ${otp ? `
                <div class="otp-box">
                    <p style="margin: 0 0 10px 0; font-size: 14px; color: #aaaaaa; letter-spacing: normal;">Your Verification Code:</p>
                    <p class="otp-code">${otp}</p>
                </div>
                <p style="font-size: 14px; color: #aaaaaa;">This code will expire in 10 minutes.</p>
                ` : ''}
            </div>
            <div class="footer">
                <p>If you didn't request this email, please ignore it.</p>
                <p>&copy; ${new Date().getFullYear()} Academic Sloth. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    `;
}

/**
 * Sends an email using the configured transporter.
 * @param {string} to - The recipient's email address
 * @param {string} subject - The subject line of the email
 * @param {string} text - The plain text fallback body
 * @param {string} html - The formatted HTML body
 */
async function sendEmail(to, subject, text, html) {
    try {
        const mailOptions = {
            from: `"Academic Sloth" <${process.env.EMAIL_USER}>`,
            to: to,
            subject: subject,
            text: text,
            html: html // Nodemailer will automatically use the HTML version if the client supports it!
        };

        const info = await transporter.sendMail(mailOptions);
        console.log(`✉️  Email sent to ${to}: ${info.messageId}`);
        return true;
    } catch (error) {
        console.error('❌ Error sending email:', error);
        throw new Error('Could not send email.');
    }
}

/**
 * Helper function to generate a random 6-digit OTP
 * @returns {string} e.g. "492015"
 */
function generateOTP() {
    const otp = Math.floor(100000 + Math.random() * 900000);
    return otp.toString();
}

module.exports = {
    sendEmail,
    generateOTP,
    getHtmlTemplate
};
