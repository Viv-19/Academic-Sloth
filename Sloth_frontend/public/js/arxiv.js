import { auth } from './auth.js';

const API_URL = 'http://localhost:3000/api/arxiv';

export const arxiv = {
    currentArxivId: null,

    init() {
        const previewBtn = document.getElementById('arxiv-preview-btn');
        const importBtn = document.getElementById('arxiv-import-btn');
        const closeBtn = document.getElementById('close-preview-btn');
        const input = document.getElementById('arxiv-id-input');
        const modal = document.getElementById('arxiv-preview-modal');

        if (!previewBtn || !input || !modal) return;

        previewBtn.addEventListener('click', async () => {
            const id = input.value.trim();
            if (!id) {
                alert('Please enter an arXiv ID (e.g. 1706.03762)');
                return;
            }
            await this.previewPaper(id);
        });

        // Allow pressing Enter in the input
        input.addEventListener('keypress', async (e) => {
            if (e.key === 'Enter') {
                const id = input.value.trim();
                if (id) await this.previewPaper(id);
            }
        });

        closeBtn.addEventListener('click', () => {
            modal.classList.add('hidden');
            modal.classList.remove('flex');
            this.currentArxivId = null;
        });

        importBtn.addEventListener('click', async () => {
            if (this.currentArxivId) {
                await this.importPaper(this.currentArxivId);
            }
        });
    },

    async previewPaper(id) {
        const previewBtn = document.getElementById('arxiv-preview-btn');
        const originalText = previewBtn.innerHTML;
        previewBtn.innerHTML = '<span class="material-symbols-outlined text-sm animate-spin">refresh</span> Loading';
        previewBtn.disabled = true;

        try {
            const response = await fetch(`${API_URL}/preview/${id}`, {
                headers: { 'Authorization': `Bearer ${auth.getToken()}` }
            });
            const data = await response.json();

            if (!response.ok) {
                alert(data.message || 'Failed to fetch preview.');
                return;
            }

            const paper = data.data;
            this.currentArxivId = paper.arxivId;

            // Populate Modal
            document.getElementById('preview-title').textContent = paper.title;
            document.getElementById('preview-authors').textContent = paper.authors.join(', ');
            document.getElementById('preview-abstract').textContent = paper.abstract;

            // Show Modal
            const modal = document.getElementById('arxiv-preview-modal');
            modal.classList.remove('hidden');
            modal.classList.add('flex');

        } catch (error) {
            console.error('Error fetching preview:', error);
            alert('A network error occurred.');
        } finally {
            previewBtn.innerHTML = originalText;
            previewBtn.disabled = false;
        }
    },

    async importPaper(id) {
        const importBtn = document.getElementById('arxiv-import-btn');
        const originalText = importBtn.innerHTML;
        importBtn.innerHTML = '<span class="material-symbols-outlined text-sm animate-spin">refresh</span> Downloading...';
        importBtn.disabled = true;

        try {
            const response = await fetch(`${API_URL}/import`, {
                method: 'POST',
                headers: { 
                    'Authorization': `Bearer ${auth.getToken()}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ arxivId: id })
            });
            const data = await response.json();

            if (!response.ok) {
                alert(data.message || 'Failed to import paper.');
                return;
            }

            alert('Paper imported successfully! It is now in your library.');
            window.location.reload();

        } catch (error) {
            console.error('Error importing paper:', error);
            alert('A network error occurred while importing.');
        } finally {
            importBtn.innerHTML = originalText;
            importBtn.disabled = false;
        }
    }
};

// Auto-initialize when the DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    arxiv.init();
});
