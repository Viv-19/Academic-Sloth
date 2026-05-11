const arxivService = require('../services/arxivService');

/**
 * Handle GET /api/arxiv/preview/:id
 */
async function getPreview(req, res, next) {
    try {
        const arxivId = req.params.id;
        if (!arxivId) {
            return res.status(400).json({ status: 'error', message: 'ArXiv ID is required.' });
        }

        const preview = await arxivService.getArxivPreview(arxivId);

        res.status(200).json({
            status: 'success',
            data: preview
        });
    } catch (error) {
        if (error.message === 'Paper not found on ArXiv.') {
            return res.status(404).json({ status: 'error', message: error.message });
        }
        next(error);
    }
}

/**
 * Handle POST /api/arxiv/import
 */
async function importPaper(req, res, next) {
    try {
        const { arxivId } = req.body;
        const userId = req.user.id; // From auth middleware

        if (!arxivId) {
            return res.status(400).json({ status: 'error', message: 'ArXiv ID is required.' });
        }

        const document = await arxivService.importArxivPaper(arxivId, userId);

        res.status(201).json({
            status: 'success',
            message: 'Paper imported successfully from ArXiv!',
            data: document
        });

    } catch (error) {
        next(error);
    }
}

/**
 * Handle GET /api/arxiv/search?q=keyword
 * 🎓 LEARNING MOMENT: Query Parameters
 * Notice how we use `req.query.q` instead of `req.params.id`. 
 * Params are for specific resources (/preview/123), whereas Queries are for 
 * filtering or searching a list of things (/search?q=Transformers).
 */
async function searchPapers(req, res, next) {
    try {
        const query = req.query.q;

        if (!query) {
            return res.status(400).json({ status: 'error', message: 'Search query is required.' });
        }

        const results = await arxivService.searchHybrid(query);

        res.status(200).json({
            status: 'success',
            data: results
        });
    } catch (error) {
        next(error);
    }
}

module.exports = {
    getPreview,
    importPaper,
    searchPapers
};
