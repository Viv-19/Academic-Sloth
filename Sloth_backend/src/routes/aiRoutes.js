/**
 * aiRoutes.js
 * 
 * 🎓 LEARNING: The Node.js backend acts as a PROXY for AI requests.
 * 
 * Why not call the Python service directly from the browser?
 * 1. Security — the browser would need to expose the JWT token to Python
 * 2. Auth — Node already has our `protect` middleware to verify JWT
 * 3. Single entry point — the frontend only needs to know about localhost:3000
 * 
 * Flow: Browser → Node.js (auth check) → Python AI Service → Browser
 * 
 * This is called the "Backend-for-Frontend" (BFF) pattern.
 */

const express = require('express');
const { protect } = require('../middlewares/authMiddleware');
const aiController = require('../controllers/aiController');

const router = express.Router();

// All AI routes require authentication
router.use(protect);

// POST /api/ai/chat
// Proxies the user's question to the Python RAG service and streams the response back
router.post('/chat', aiController.chatWithPaper);

// POST /api/ai/ingest/:docId
// Triggers background ingestion of a document into the vector store
router.post('/ingest/:docId', aiController.ingestDocument);

// GET /api/ai/health
// Checks if the Python AI service is alive
router.get('/health', aiController.checkAiHealth);

module.exports = router;
