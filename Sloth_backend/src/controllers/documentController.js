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

        // 4. Send success response back to the client
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

module.exports = {
    uploadDocument,
    getMyDocuments
};
