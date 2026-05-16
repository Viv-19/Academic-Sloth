/**
 * paper_review.js
 * 
 * 🎓 LEARNING MOMENT: This module handles the entire Paper Review page logic:
 * 1. init()              — Reads URL ?id= param, fetches metadata, renders the PDF
 * 2. loadPaper()         — Takes a paper object and swaps the PDF in the middle pane (SPA-style, no page reload)
 * 3. loadSidebarPapers() — Fetches all user papers and renders them as clickable items in the sidebar
 *
 * The key idea is "DOM manipulation without navigation" — when the user clicks a paper in the sidebar,
 * we update the <iframe> src attribute directly instead of navigating to a new URL.
 * This keeps the chat history alive and provides a seamless experience.
 */

const API_URL = 'http://localhost:3000/api';

export const paperReview = {

    // Track the currently active document ID so we can highlight it in the sidebar
    currentDocId: null,

    /**
     * Called once on page load. Reads the ?id= from the URL and loads that paper.
     */
    async init(token) {
        const params = new URLSearchParams(window.location.search);
        const docId = params.get('id');

        if (!docId) {
            // No id in URL — show empty state, user will click from sidebar
            this.showEmptyState();
            return;
        }

        try {
            const response = await fetch(`${API_URL}/documents/${docId}`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (!response.ok) {
                this.showError('Could not load this paper. It may have been deleted.');
                return;
            }

            const data = await response.json();
            this.loadPaper(data.data, token);

        } catch (error) {
            console.error('Error loading paper:', error);
            this.showError('A network error occurred while loading the paper.');
        }
    },

    /**
     * Renders a specific paper in the middle pane.
     * 
     * 🎓 LEARNING MOMENT: This is the core SPA pattern!
     * Instead of navigating to a new page, we directly:
     * 1. Extract the filename from the stored path
     * 2. Build the correct /uploads/ URL
     * 3. Update the browser's address bar with history.pushState (optional, keeps URL in sync)
     * 4. Inject an <iframe> into the middle pane
     * 
     * @param {object} paper - The document object from the API
     * @param {string} token - JWT auth token (not used for iframe but kept for consistency)
     */
    loadPaper(paper, token) {
        this.currentDocId = paper.id;

        // Update page title
        document.title = `${paper.title} - Academic Sloth`;

        // Update the browser URL bar without reloading the page
        // history.pushState keeps navigation history intact (back button works)
        history.pushState({}, '', `paper_review.html?id=${paper.id}`);

        // Build the correct PDF URL:
        // DB stores: "C:\Users\...\uploads\filename.pdf" (absolute Windows path)
        // We need: "http://localhost:3000/uploads/filename.pdf"
        // So we just extract the filename portion using split on both / and \
        const fileName = paper.file_path.split(/[\/\\]/).pop();
        const pdfUrl = `http://localhost:3000/uploads/${encodeURIComponent(fileName)}`;

        // Inject the full-height PDF iframe into the middle pane
        const contentArea = document.getElementById('paper-content');
        contentArea.innerHTML = `
            <iframe
                src="${pdfUrl}"
                class="w-full h-full border-0"
                title="${paper.title}"
                style="display: block;"
            >
                <p class="text-white/60 p-4">
                    Your browser could not display this PDF inline.
                    <a href="${pdfUrl}" target="_blank" class="text-primary underline">Open in new tab.</a>
                </p>
            </iframe>
        `;

        // Highlight the active paper in the sidebar
        this.updateSidebarActiveState(paper.id);

        // Notify the page that a paper was loaded (for chat clearing + ingestion trigger)
        if (typeof this.onPaperLoad === 'function') {
            this.onPaperLoad(paper);
        }
    },

    /**
     * Fetches all user papers and renders them as a clickable list in the sidebar.
     * Each item click calls loadPaper() to swap the PDF without any page navigation.
     */
    async loadSidebarPapers(token) {
        const container = document.getElementById('sidebar-papers');
        if (!container) return;

        try {
            const response = await fetch(`${API_URL}/documents`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });

            const data = await response.json();
            if (!response.ok || !data.data) {
                container.innerHTML = `<p class="text-white/30 text-xs px-2">Could not load papers.</p>`;
                return;
            }

            const papers = data.data;

            if (papers.length === 0) {
                container.innerHTML = `
                    <div class="text-center py-4 px-2">
                        <p class="text-white/30 text-xs leading-relaxed">No papers yet. Upload one using the button above!</p>
                    </div>`;
                return;
            }

            container.innerHTML = '';

            papers.forEach(paper => {
                const item = document.createElement('button');

                // 🎓 LEARNING MOMENT: 'paper-item' is a class we use to select all sidebar
                // paper items when updating the active state highlight below.
                item.className = 'paper-item w-full text-left px-3 py-2 rounded-lg hover:bg-white/5 border border-transparent transition-all group flex items-start gap-2';
                item.dataset.id = paper.id;

                // Determine source badge
                const badge = paper.source === 'arxiv'
                    ? `<span class="text-[9px] bg-blue-500/10 text-blue-400 border border-blue-500/20 px-1.5 py-0.5 rounded-full font-medium">arXiv</span>`
                    : `<span class="text-[9px] bg-white/5 text-white/30 border border-white/10 px-1.5 py-0.5 rounded-full font-medium">PDF</span>`;

                item.innerHTML = `
                    <span class="material-symbols-outlined text-[16px] text-white/30 group-hover:text-primary/60 transition-colors mt-0.5 shrink-0">description</span>
                    <div class="flex flex-col min-w-0 gap-1 flex-1">
                        <span class="paper-item-title text-white/70 group-hover:text-white text-xs font-medium leading-snug transition-colors line-clamp-2">${paper.title}</span>
                        ${badge}
                    </div>
                `;

                // When clicked: load this paper in the middle pane (no navigation!)
                item.addEventListener('click', () => {
                    this.loadPaper(paper, token);
                });

                container.appendChild(item);
            });

            // Highlight the currently active paper if one is loaded
            if (this.currentDocId) {
                this.updateSidebarActiveState(this.currentDocId);
            }

        } catch (error) {
            console.error('Error loading sidebar papers:', error);
            container.innerHTML = `<p class="text-white/30 text-xs px-2">Network error.</p>`;
        }
    },

    /**
     * Highlights the currently active paper in the sidebar list.
     * Removes the active class from all items, then adds it to the matching one.
     */
    updateSidebarActiveState(docId) {
        // Remove active state from all items
        document.querySelectorAll('.paper-item').forEach(el => el.classList.remove('active'));

        // Add active state to the matching item
        const activeItem = document.querySelector(`.paper-item[data-id="${docId}"]`);
        if (activeItem) {
            activeItem.classList.add('active');
            // Smoothly scroll the item into view in case the list is long
            activeItem.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    },

    /**
     * Shows an empty/welcome state when no paper is selected yet.
     */
    showEmptyState() {
        const contentArea = document.getElementById('paper-content');
        if (contentArea) {
            contentArea.innerHTML = `
                <div class="flex flex-col items-center justify-center h-full gap-4 text-center">
                    <span class="material-symbols-outlined text-6xl text-white/10">menu_book</span>
                    <p class="text-white/30 text-lg">Select a paper from the sidebar to start reading</p>
                </div>
            `;
        }
    },

    /**
     * Shows an error state in the middle pane.
     */
    showError(message) {
        const contentArea = document.getElementById('paper-content');
        if (contentArea) {
            contentArea.innerHTML = `
                <div class="flex flex-col items-center justify-center h-full text-center gap-4">
                    <span class="material-symbols-outlined text-5xl text-red-400">error</span>
                    <p class="text-white/60">${message}</p>
                    <a href="library.html" class="px-4 py-2 rounded-lg bg-primary/20 text-primary border border-primary/30 hover:bg-primary/40 transition-colors text-sm font-medium">
                        Back to Library
                    </a>
                </div>
            `;
        }
    }
};
