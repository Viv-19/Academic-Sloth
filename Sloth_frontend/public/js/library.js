import { auth } from './auth.js';

const API_URL = 'http://localhost:3000/api/documents';

export const library = {

    /**
     * Fetches and displays recent papers on the dashboard.
     * Each paper card is now clickable and routes to paper_review.html?id=...
     */
    async loadRecentPapers(containerId) {
        const container = document.getElementById(containerId);
        if (!container) return;

        try {
            const response = await fetch(API_URL, {
                headers: { 'Authorization': `Bearer ${auth.getToken()}` }
            });
            const data = await response.json();

            if (!response.ok) return;

            container.innerHTML = '';

            if (data.data.length === 0) {
                container.innerHTML = `<p class="text-white/60">No papers uploaded yet. Upload a PDF or import from ArXiv to get started!</p>`;
                return;
            }

            // Render the fetched papers (take latest 6 for the dashboard)
            data.data.slice(0, 6).forEach(doc => {
                const date = new Date(doc.created_at).toLocaleDateString();
                const card = document.createElement('div');
                card.className = "flex flex-col gap-2 p-4 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 transition-all cursor-pointer hover:border-primary/30 hover:shadow-md hover:shadow-primary/5 group";
                
                // 🎓 LEARNING MOMENT: When the card is clicked, we navigate to paper_review.html
                // and pass the document ID as a URL query parameter.
                // The paper_review page will then read this ID and load the correct paper.
                card.onclick = () => {
                    window.location.href = `paper_review.html?id=${doc.id}`;
                };

                card.innerHTML = `
                    <div class="flex justify-between items-start gap-2">
                        <h3 class="text-white text-base font-semibold line-clamp-2 flex-1 group-hover:text-primary transition-colors">${doc.title}</h3>
                        <span class="material-symbols-outlined text-white/30 group-hover:text-primary/60 transition-colors text-xl shrink-0">arrow_forward</span>
                    </div>
                    <p class="text-white/60 text-sm">Status: <span class="capitalize ${doc.status === 'pending' ? 'text-yellow-500' : 'text-green-500'}">${doc.status}</span></p>
                    <p class="text-white/50 text-xs">Added: ${date}</p>
                `;

                container.appendChild(card);
            });

        } catch (error) {
            console.error('Error loading recent papers:', error);
        }
    },

    /**
     * Loads the full library (all papers) with a clickable grid layout.
     */
    async loadLibrary(containerId) {
        const container = document.getElementById(containerId);
        if (!container) return;

        container.innerHTML = `<div class="flex justify-center col-span-full py-10"><span class="material-symbols-outlined text-4xl text-primary animate-spin">refresh</span></div>`;

        try {
            const response = await fetch(API_URL, {
                headers: { 'Authorization': `Bearer ${auth.getToken()}` }
            });
            const data = await response.json();

            if (!response.ok) {
                container.innerHTML = '<p class="text-red-400">Could not load library.</p>';
                return;
            }

            container.innerHTML = '';

            if (data.data.length === 0) {
                container.innerHTML = `
                    <div class="col-span-full flex flex-col items-center justify-center gap-4 py-20 text-center">
                        <span class="material-symbols-outlined text-6xl text-white/20">menu_book</span>
                        <p class="text-white/40 text-lg">Your library is empty</p>
                        <a href="dashboard.html" class="px-4 py-2 rounded-lg bg-primary/20 text-primary border border-primary/30 hover:bg-primary/40 transition-colors text-sm">
                            Go to Dashboard to Add Papers
                        </a>
                    </div>`;
                return;
            }

            data.data.forEach(doc => {
                const date = new Date(doc.created_at).toLocaleDateString();
                const card = document.createElement('div');
                card.className = "flex flex-col gap-3 p-5 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 transition-all cursor-pointer hover:border-primary/30 hover:shadow-md hover:shadow-primary/5 group";
                
                card.onclick = () => {
                    window.location.href = `paper_review.html?id=${doc.id}`;
                };

                card.innerHTML = `
                    <div class="flex items-start justify-between gap-2">
                        <h3 class="text-white text-base font-semibold line-clamp-2 flex-1 group-hover:text-primary transition-colors">${doc.title}</h3>
                        <span class="material-symbols-outlined text-white/30 group-hover:text-primary/60 transition-colors text-xl shrink-0">open_in_new</span>
                    </div>
                    <p class="text-white/50 text-xs mt-auto">Added: ${date}</p>
                    <div class="flex items-center gap-2 mt-1">
                        <span class="px-2 py-1 rounded text-xs ${doc.status === 'pending' ? 'bg-yellow-500/10 text-yellow-500 border border-yellow-500/20' : 'bg-green-500/10 text-green-500 border border-green-500/20'} capitalize font-medium">${doc.status}</span>
                        ${doc.source === 'arxiv' ? `<span class="px-2 py-1 rounded text-xs bg-blue-500/10 text-blue-400 border border-blue-500/20 font-medium">arXiv</span>` : ''}
                    </div>
                `;
                container.appendChild(card);
            });

        } catch (error) {
            console.error('Error loading library:', error);
            container.innerHTML = '<p class="text-red-400 col-span-full">A network error occurred.</p>';
        }
    },

    /**
     * Loads library stats into the provided element IDs.
     */
    async loadStats(totalId, monthlyId, chatId) {
        try {
            const response = await fetch(API_URL, {
                headers: { 'Authorization': `Bearer ${auth.getToken()}` }
            });
            const data = await response.json();
            if (!response.ok) return;

            const allDocs = data.data;
            const now = new Date();
            const monthlyDocs = allDocs.filter(d => {
                const created = new Date(d.created_at);
                return created.getMonth() === now.getMonth() && created.getFullYear() === now.getFullYear();
            });

            const totalEl = document.getElementById(totalId);
            const monthlyEl = document.getElementById(monthlyId);
            const chatEl = document.getElementById(chatId);

            if (totalEl) totalEl.textContent = allDocs.length;
            if (monthlyEl) monthlyEl.textContent = monthlyDocs.length;
            if (chatEl) chatEl.textContent = '0'; // Placeholder until Chat is built

        } catch (error) {
            console.error('Error loading stats:', error);
        }
    },

    /**
     * Sorts the library cards in-memory.
     */
    sortLibrary(sortBy, containerId) {
        // This will be enhanced once we have a richer data model.
        console.log(`Sorting by ${sortBy}`);
    }
};
