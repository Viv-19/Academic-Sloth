const documentService = require('../services/documentService');

/**
 * Handle POST /api/documents/upload
 * This endpoint receives a multipart/form-data request containing a PDF.
 */
async function uploadDocument(req, res, next) {
    try {
        // 1. Check if Multer successfully processed a file
        if (!req.file) {
            return res.status(400).json({ status: 'error', message: 'No PDF file uploaded. Please select a file.' });
        }

        // 2. Extract information from the request
        const userId = req.user.id; // This comes from our authMiddleware! We know EXACTLY who uploaded it.
        const filePath = req.file.path; // The physical location where Multer saved the file (e.g., 'uploads/123-paper.pdf')
        const title = req.file.originalname; // The original name of the file

        // 3. Save the document metadata to the database
        const document = await documentService.createDocumentRecord(userId, title, filePath);

        // 4. Auto-trigger ingestion in the Python AI service (fire-and-forget)
        //    This means the paper is indexed immediately after upload — the user
        //    doesn't need to manually open it in paper_review first.
        const AI_SERVICE_URL = process.env.AI_SERVICE_URL || 'http://localhost:8000/api';
        fetch(`${AI_SERVICE_URL}/ingest`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                doc_id: document.id,
                file_path: document.file_path,
                title: document.title,
            }),
        }).catch(err => console.log('[Upload] AI ingest queued (fire-and-forget):', err.message));

        // 5. Send success response back to the client
        res.status(201).json({
            status: 'success',
            message: 'Document uploaded successfully and is pending AI processing.',
            data: document
        });

    } catch (error) {
        // Pass any unexpected errors to the global error handler
        next(error);
    }
}

/**
 * Handle GET /api/documents
 * Returns all documents for the logged-in user.
 */
async function getMyDocuments(req, res, next) {
    try {
        const userId = req.user.id;
        const documents = await documentService.getUserDocuments(userId);

        res.status(200).json({
            status: 'success',
            data: documents
        });
    } catch (error) {
        next(error);
    }
}

/**
 * Handle GET /api/documents/:id
 * Returns the metadata for a single document, verifying ownership.
 */
async function getDocumentById(req, res, next) {
    try {
        const userId = req.user.id;
        const docId = req.params.id; // The :id from the URL (e.g. /api/documents/cm4xyz123)

        const document = await documentService.getDocumentById(docId, userId);

        if (!document) {
            // Return 404 if not found OR if it belongs to a different user
            return res.status(404).json({ status: 'error', message: 'Document not found.' });
        }

        res.status(200).json({ status: 'success', data: document });
    } catch (error) {
        next(error);
    }
}

/**
 * Handle PATCH /api/documents/:id/status
 * Called by the Python AI service after ingestion completes.
 * Updates the document status to 'indexed' or 'failed'.
 */
async function updateDocumentStatus(req, res, next) {
    try {
        const { id } = req.params;
        const { status } = req.body;

        const allowed = ['pending', 'indexed', 'failed'];
        if (!allowed.includes(status)) {
            return res.status(400).json({ status: 'error', message: `Invalid status. Must be one of: ${allowed.join(', ')}` });
        }

        const updated = await documentService.updateStatus(id, status);
        res.status(200).json({ status: 'success', data: updated });
    } catch (error) {
        next(error);
    }
}

module.exports = {
    uploadDocument,
    getMyDocuments,
    getDocumentById,
    updateDocumentStatus
};
