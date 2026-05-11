import { auth } from './auth.js';

export const library = {
    /**
     * Stub to fetch and display recent papers on the dashboard.
     * We will build out the actual UI rendering in Phase 1.4/1.5.
     */
    async loadRecentPapers(containerId) {
        const container = document.getElementById(containerId);
        if (!container) return;

        try {
            // Fetch documents from the backend
            const response = await fetch('http://localhost:3000/api/documents', {
                headers: {
                    'Authorization': `Bearer ${auth.getToken()}`
                }
            });
            const data = await response.json();

            if (!response.ok) return;

            // Clear the placeholder UI
            container.innerHTML = '';

            if (data.data.length === 0) {
                container.innerHTML = `<p class="text-white/60">No papers uploaded yet. Upload a PDF to get started!</p>`;
                return;
            }

            // Render the fetched papers
            data.data.forEach(doc => {
                const date = new Date(doc.created_at).toLocaleDateString();
                const html = `
                <div class="flex flex-col gap-2 p-4 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 transition-colors cursor-pointer">
                    <h3 class="text-white text-base font-semibold line-clamp-2">${doc.title}</h3>
                    <p class="text-white/60 text-sm">Status: <span class="capitalize ${doc.status === 'pending' ? 'text-yellow-500' : 'text-green-500'}">${doc.status}</span></p>
                    <p class="text-white/50 text-xs">Added: ${date}</p>
                </div>`;
                container.innerHTML += html;
            });

        } catch (error) {
            console.error('Error loading papers:', error);
        }
    }
};
