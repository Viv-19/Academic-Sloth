const express = require('express');
const documentController = require('../controllers/documentController');
const { protect } = require('../middlewares/authMiddleware');
const upload = require('../middlewares/uploadMiddleware');

const router = express.Router();

// ─────────────────────────────────────────────────────────────────────────────
// INTERNAL ROUTE (no JWT required) — must be registered BEFORE router.use(protect)
//
// 🎓 LEARNING: Express processes middleware and routes in the ORDER they are
// registered. `router.use(protect)` applies to every route defined AFTER it.
// By placing this PATCH route BEFORE the router.use(protect) call, it bypasses
// authentication entirely.
//
// This is the standard pattern for internal service-to-service routes:
// the Python AI service has no user JWT, but it needs to update document status.
//
// In production, you'd secure this with a shared internal secret:
//   if (req.headers['x-internal-secret'] !== process.env.INTERNAL_SECRET) return 401
// ─────────────────────────────────────────────────────────────────────────────
router.patch('/:id/status', documentController.updateDocumentStatus);

// Apply JWT protection to all routes defined AFTER this line
router.use(protect);

// POST /api/documents/upload
router.post('/upload', upload.single('pdfFile'), documentController.uploadDocument);

// GET /api/documents — list all user's documents
router.get('/', documentController.getMyDocuments);

// GET /api/documents/:id — get one document (ownership verified in controller)
router.get('/:id', documentController.getDocumentById);

module.exports = router;
