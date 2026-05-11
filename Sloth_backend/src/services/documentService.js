const prisma = require('../config/db');

/**
 * Saves a new uploaded document's metadata to the database.
 * @param {string} userId - The ID of the user who uploaded the document
 * @param {string} title - The original filename or given title
 * @param {string} filePath - The local path where the file is stored
 * @returns {object} The created document record
 */
async function createDocumentRecord(userId, title, filePath) {
    try {
        // Create a new row in the Document table
        const document = await prisma.document.create({
            data: {
                title: title,
                file_path: filePath,
                status: 'pending', // Starts as pending until the AI processes it
                user_id: userId
            }
        });

        // 🚀 FUTURE PHASE: Here is where we will trigger a background job 
        // to send the file to the Python AI service for processing!
        console.log(`Document created: ${document.id}. Ready for AI processing.`);

        return document;
    } catch (error) {
        console.error('❌ Error saving document to DB:', error);
        throw new Error('Could not save document metadata.');
    }
}

/**
 * Retrieves all documents for a specific user.
 * @param {string} userId - The ID of the user
 */
async function getUserDocuments(userId) {
    return await prisma.document.findMany({
        where: { user_id: userId },
        orderBy: { created_at: 'desc' } // Newest first
    });
}

module.exports = {
    createDocumentRecord,
    getUserDocuments
};
