const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const morgan = require('morgan');
const path = require('path');

// Initialize the Express application
const app = express();

// Serve Frontend Static Files
app.use(express.static(path.join(__dirname, '../../Sloth_frontend/public')));

// --- Middlewares ---
// 1. Helmet helps secure Express apps by setting HTTP response headers.
app.use(helmet());

// 2. CORS (Cross-Origin Resource Sharing) allows our frontend to communicate with this backend.
app.use(cors());

// 3. Morgan logs the incoming HTTP requests to the console (useful for debugging).
app.use(morgan('dev'));

// 4. Built-in middleware to parse incoming JSON payloads.
app.use(express.json());

// 5. Built-in middleware to parse URL-encoded data.
app.use(express.urlencoded({ extended: true }));

// --- Routes ---
const authRoutes = require('./routes/authRoutes');

// Mount routes
app.use('/api/auth', authRoutes);

// A simple Health Check endpoint. This is standard in production to let load balancers
// or Docker know that the service is alive and running successfully.
// When a GET request hits '/health', we send back a 200 OK status and a JSON object.
app.get('/health', (req, res) => {
    res.status(200).json({
        status: 'success',
        message: 'ResearchOS Backend is running.',
        timestamp: new Date().toISOString()
    });
});

// --- Global Error Handler ---
// This is a special middleware with 4 arguments: (err, req, res, next)
// Express recognizes it as an error handler because of these 4 arguments.
// If any route or middleware throws an error, it will be caught here instead of crashing the server.
app.use((err, req, res, next) => {
    console.error('❌ Server Error:', err.stack); // Log the full error trace for debugging

    // Send a user-friendly error response back to the client
    res.status(500).json({
        status: 'error',
        message: 'Something went wrong on the server!'
    });
});

// We will add more routes here soon!

// Export the app so it can be imported in server.js
module.exports = app;
