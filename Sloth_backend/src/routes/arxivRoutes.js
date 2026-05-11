const express = require('express');
const arxivController = require('../controllers/arxivController');
const { protect } = require('../middlewares/authMiddleware');

const router = express.Router();

// Apply auth middleware - user must be logged in to interact with ArXiv
router.use(protect);

// GET /api/arxiv/preview/:id
router.get('/preview/:id', arxivController.getPreview);

// GET /api/arxiv/search?q=keyword
router.get('/search', arxivController.searchPapers);

// POST /api/arxiv/import
router.post('/import', arxivController.importPaper);

module.exports = router;
