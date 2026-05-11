const express = require('express');
const documentController = require('../controllers/documentController');
const { protect } = require('../middlewares/authMiddleware');
const upload = require('../middlewares/uploadMiddleware');

const router = express.Router();

// Apply the 'protect' middleware to ALL routes in this file.
// This means you MUST be logged in (have a valid JWT token) to upload or view documents.
router.use(protect);

// POST /api/documents/upload
// The upload.single('pdfFile') middleware intercepts the request, grabs the file named "pdfFile",
// saves it to disk, and attaches the file info to `req.file` before passing it to our controller.
router.post('/upload', upload.single('pdfFile'), documentController.uploadDocument);

// GET /api/documents
// Retrieves a list of all documents uploaded by the user
router.get('/', documentController.getMyDocuments);

module.exports = router;
