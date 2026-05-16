/**
 * aiController.js
 * 
 * 🎓 LEARNING: This controller is a PROXY — it sits between the browser
 * and the Python AI service. Its jobs are:
 * 1. Verify the user is authenticated (done by `protect` middleware)
 * 2. Forward the request to the Python service with the right params
 * 3. Stream the response back to the browser
 * 
 * We use the native `fetch` API (available in Node 18+) for streaming.
 */

const documentService = require('../services/documentService');

const AI_SERVICE_URL = process.env.AI_SERVICE_URL || 'http://localhost:8000/api';

/**
 * POST /api/ai/chat
 * Streams a RAG-grounded answer from the Python AI service.
 */
async function chatWithPaper(req, res, next) {
    try {
        const { doc_id, question, chat_history = [] } = req.body;

        if (!doc_id || !question) {
            return res.status(400).json({ status: 'error', message: 'doc_id and question are required.' });
        }

        // Security check: verify this document belongs to the requesting user
        const document = await documentService.getDocumentById(doc_id, req.user.id);
        if (!document) {
            return res.status(404).json({ status: 'error', message: 'Document not found.' });
        }

        // 🎓 LEARNING: Set up Server-Sent Events (SSE) headers.
        // These tell the browser to keep the connection open and
        // treat each incoming line as a separate "event".
        res.setHeader('Content-Type', 'text/event-stream');
        res.setHeader('Cache-Control', 'no-cache');
        res.setHeader('Connection', 'keep-alive');
        res.setHeader('X-Accel-Buffering', 'no');
        res.flushHeaders(); // Send headers immediately

        // Forward request to Python AI service
        const aiResponse = await fetch(`${AI_SERVICE_URL}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ doc_id, question, chat_history }),
        });

        if (!aiResponse.ok) {
            res.write(`data: ${JSON.stringify({ type: 'error', content: 'AI service error.' })}\n\n`);
            res.end();
            return;
        }

        // 🎓 LEARNING: Pipe the streaming response from Python → Browser.
        // We read the Python stream chunk by chunk and write each chunk
        // directly to the browser's open SSE connection.
        const reader = aiResponse.body.getReader();
        const decoder = new TextDecoder();

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            res.write(decoder.decode(value, { stream: true }));
        }

        res.end();

    } catch (error) {
        console.error('❌ AI Chat Proxy Error:', error.message);
        // If headers already sent (streaming started), we can't send a JSON error
        if (!res.headersSent) {
            next(error);
        } else {
            res.write(`data: ${JSON.stringify({ type: 'error', content: 'Stream interrupted.' })}\n\n`);
            res.end();
        }
    }
}

/**
 * POST /api/ai/ingest/:docId
 * Triggers background ingestion of a PDF into the vector store.
 */
async function ingestDocument(req, res, next) {
    try {
        const { docId } = req.params;

        // Verify ownership
        const document = await documentService.getDocumentById(docId, req.user.id);
        if (!document) {
            return res.status(404).json({ status: 'error', message: 'Document not found.' });
        }

        // Fire off ingestion request to Python (don't await — it's background)
        fetch(`${AI_SERVICE_URL}/ingest`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                doc_id: document.id,
                file_path: document.file_path,
                title: document.title,
            }),
        }).catch(err => console.error('AI ingest error:', err.message));

        res.status(202).json({
            status: 'accepted',
            message: 'Document ingestion started in the background.',
            doc_id: docId,
        });

    } catch (error) {
        next(error);
    }
}

/**
 * GET /api/ai/health
 * Checks whether the Python AI service is reachable and healthy.
 */
async function checkAiHealth(req, res, next) {
    try {
        const response = await fetch(`${AI_SERVICE_URL}/health`);
        const data = await response.json();
        res.status(response.ok ? 200 : 503).json(data);
    } catch (error) {
        res.status(503).json({
            status: 'unreachable',
            message: 'Python AI service is not running.',
            url: AI_SERVICE_URL,
        });
    }
}

module.exports = { chatWithPaper, ingestDocument, checkAiHealth };
