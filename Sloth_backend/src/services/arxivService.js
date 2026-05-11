const axios = require('axios');
const { XMLParser } = require('fast-xml-parser');
const fs = require('fs');
const path = require('path');
const prisma = require('../config/db');

// We use this parser to easily convert the messy XML from ArXiv into a clean JSON object
const parser = new XMLParser({
    ignoreAttributes: false,
    attributeNamePrefix: "@_"
});

/**
 * Fetches metadata (Title, Abstract, Authors, PDF link) from ArXiv using the Paper ID
 * @param {string} arxivId - e.g., "1706.03762"
 */
async function getArxivPreview(arxivId) {
    try {
        const url = `http://export.arxiv.org/api/query?id_list=${arxivId}`;
        const response = await axios.get(url);
        
        // Parse the XML response into JSON
        const data = parser.parse(response.data);
        const entry = data.feed.entry;

        if (!entry) {
            throw new Error('Paper not found on ArXiv.');
        }

        // Clean up the authors list
        let authors = [];
        if (Array.isArray(entry.author)) {
            authors = entry.author.map(a => a.name);
        } else if (entry.author) {
            authors = [entry.author.name];
        }

        // Find the PDF link
        let pdfLink = null;
        if (Array.isArray(entry.link)) {
            const pdfObj = entry.link.find(l => l['@_title'] === 'pdf' || l['@_type'] === 'application/pdf');
            if (pdfObj) pdfLink = pdfObj['@_href'];
        }

        // Clean title (remove newlines)
        const cleanTitle = entry.title.replace(/\n/g, ' ').replace(/\s+/g, ' ').trim();

        return {
            arxivId: arxivId,
            title: cleanTitle,
            abstract: entry.summary.trim(),
            authors: authors,
            published: entry.published,
            pdfLink: pdfLink
        };
    } catch (error) {
        console.error('Error fetching ArXiv metadata:', error);
        throw new Error('Failed to fetch data from ArXiv.');
    }
}

/**
 * Downloads the PDF directly from ArXiv and saves it to the DB as a Document
 * @param {string} arxivId - The ArXiv ID
 * @param {string} userId - The user who is importing this paper
 */
async function importArxivPaper(arxivId, userId) {
    try {
        // 1. Fetch metadata to get the PDF link and Title
        const metadata = await getArxivPreview(arxivId);
        
        if (!metadata.pdfLink) {
            throw new Error('No PDF link found for this ArXiv ID.');
        }

        // ArXiv sometimes returns http://... we should enforce https:// for security if possible, 
        // but axios handles redirects. We append '.pdf' so it directly downloads.
        let downloadUrl = metadata.pdfLink;
        if (!downloadUrl.endsWith('.pdf')) {
            downloadUrl += '.pdf';
        }

        // 2. Set up the file saving location
        const fileName = `arxiv-${arxivId}-${Date.now()}.pdf`;
        const uploadDir = path.join(__dirname, '../../../Sloth_backend/uploads');
        if (!fs.existsSync(uploadDir)) {
            fs.mkdirSync(uploadDir, { recursive: true });
        }
        const filePath = path.join(uploadDir, fileName);

        // 3. Download the PDF as a stream
        console.log(`Downloading ${downloadUrl}...`);
        const response = await axios({
            method: 'GET',
            url: downloadUrl,
            responseType: 'stream'
        });

        // Save the stream to our hard drive
        const writer = fs.createWriteStream(filePath);
        response.data.pipe(writer);

        // We wrap the writing process in a Promise so we can wait for it to finish!
        await new Promise((resolve, reject) => {
            writer.on('finish', resolve);
            writer.on('error', reject);
        });

        console.log(`Download complete: ${fileName}`);

        // 4. Save metadata to Database
        const document = await prisma.document.create({
            data: {
                title: metadata.title,
                file_path: filePath,
                status: 'pending',
                source: 'arxiv',
                arxiv_id: arxivId,
                user_id: userId
            }
        });

        return document;
    } catch (error) {
        console.error('Error importing ArXiv paper:', error);
        throw new Error('Failed to import paper from ArXiv.');
    }
}

/**
 * 🎓 LEARNING MOMENT: The "Hybrid" Architecture
 * We permanently append `+AND+cat:cs.*` to ensure we only get Computer Science / AI papers!
 * 
 * @param {string} query - The search term (e.g. "Transformers")
 */
async function searchHybrid(query) {
    try {
        console.log(`[1/3] Searching ArXiv for: ${query}`);
        
        // 1. Ask ArXiv for the top 30 papers matching the keyword IN THE CS DOMAIN ONLY.
        // We encode the query and append the category filter.
        const encodedQuery = encodeURIComponent(`all:${query}+AND+cat:cs.*`);
        const arxivUrl = `http://export.arxiv.org/api/query?search_query=${encodedQuery}&start=0&max_results=30&sortBy=relevance`;
        
        const arxivResponse = await axios.get(arxivUrl);
        const data = parser.parse(arxivResponse.data);
        
        // If there are no entries, return an empty array
        if (!data.feed.entry) return [];
        
        // Sometimes ArXiv returns a single object if there's only 1 result, 
        // so we force it into an array format for easier processing.
        const entries = Array.isArray(data.feed.entry) ? data.feed.entry : [data.feed.entry];

        // 2. Clean up the ArXiv data into a nice array of objects
        const papers = entries.map(entry => {
            // Extract the pure ID from the ArXiv URL (e.g., http://arxiv.org/abs/1706.03762v5 -> 1706.03762)
            const idMatch = entry.id.match(/abs\/(.+?)(v\d+)?$/);
            const pureId = idMatch ? idMatch[1] : entry.id;

            let authors = [];
            if (Array.isArray(entry.author)) {
                authors = entry.author.map(a => a.name);
            } else if (entry.author) {
                authors = [entry.author.name];
            }

            return {
                arxivId: pureId,
                title: entry.title.replace(/\n/g, ' ').replace(/\s+/g, ' ').trim(),
                abstract: entry.summary.trim(),
                authors: authors,
                published: entry.published,
                citationCount: 0 // Default to 0 until Semantic Scholar gives us the real number
            };
        });

        console.log(`[2/3] Found ${papers.length} papers. Asking Semantic Scholar for citations...`);

        // 3. Prepare the batch request for Semantic Scholar
        // Semantic Scholar requires ArXiv IDs to be prefixed with "ARXIV:"
        const semanticScholarIds = papers.map(p => `ARXIV:${p.arxivId}`);
        
        // 4. Hit the Semantic Scholar API!
        // We use a POST request to their /batch endpoint, which lets us ask for 30 papers at once.
        try {
            const ssResponse = await axios.post(
                'https://api.semanticscholar.org/graph/v1/paper/batch?fields=citationCount',
                { ids: semanticScholarIds }
            );

            // 5. Merge the citation counts back into our original list of papers
            const ssData = ssResponse.data; // This is an array of responses that matches our requested IDs
            
            papers.forEach((paper, index) => {
                const ssPaper = ssData[index];
                // If Semantic Scholar found the paper, update the citation count
                if (ssPaper && ssPaper.citationCount !== undefined) {
                    paper.citationCount = ssPaper.citationCount;
                }
            });
        } catch (ssError) {
            // 🎓 LEARNING MOMENT: Graceful Degradation
            // If Semantic Scholar crashes or rate-limits us, we don't want the whole app to break!
            // We just catch the error, log it, and continue. The papers will just show 0 citations.
            console.warn('Semantic Scholar API failed, falling back to 0 citations.', ssError.message);
        }

        console.log(`[3/3] Sorting papers by citation count...`);

        // 6. Sort the array purely by mathematical citation count (Highest to Lowest)
        papers.sort((a, b) => b.citationCount - a.citationCount);

        // 7. Return only the top 10 best papers
        return papers.slice(0, 10);

    } catch (error) {
        console.error('Error during hybrid search:', error);
        throw new Error('Failed to perform search.');
    }
}

module.exports = {
    getArxivPreview,
    importArxivPaper,
    searchHybrid
};
