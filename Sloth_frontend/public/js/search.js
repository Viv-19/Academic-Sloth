import { auth } from './auth.js';
import { arxiv } from './arxiv.js';

const API_URL = 'http://localhost:3000/api/arxiv';

export const search = {
    /**
     * Performs the hybrid search query to the backend and renders the results.
     * @param {string} query - The search term
     * @param {string} containerId - The ID of the div where results will be injected
     * @param {string} countId - The ID of the element to show the result count
     */
    async performSearch(query, containerId, countId) {
        const container = document.getElementById(containerId);
        const countElement = document.getElementById(countId);

        if (!container || !countElement) return;

        // Set Loading State
        countElement.textContent = 'Searching arXiv (CS domains) and sorting by citations...';
        container.innerHTML = `
            <div class="flex justify-center py-10">
                <span class="material-symbols-outlined text-4xl text-primary animate-spin">refresh</span>
            </div>
        `;

        try {
            // Hit our new hybrid backend search API
            const response = await fetch(`${API_URL}/search?q=${encodeURIComponent(query)}`, {
                headers: { 'Authorization': `Bearer ${auth.getToken()}` }
            });
            const data = await response.json();

            if (!response.ok) {
                container.innerHTML = `<p class="text-red-400">Error: ${data.message}</p>`;
                countElement.textContent = 'Search failed.';
                return;
            }

            const papers = data.data;

            if (papers.length === 0) {
                container.innerHTML = `<p class="text-white/60 text-center py-10">No Computer Science/AI papers found for "${query}". Try different keywords!</p>`;
                countElement.textContent = '0 Results';
                return;
            }

            // Update result count
            countElement.textContent = `Found ${papers.length} high-impact papers in CS/AI`;

            // Clear loading spinner
            container.innerHTML = '';

            // Render each paper card dynamically
            papers.forEach((paper, index) => {
                // Extract the year for display
                const year = new Date(paper.published).getFullYear();
                
                // Create the card container
                const card = document.createElement('div');
                card.className = "flex flex-col gap-2 p-6 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 transition-colors relative group";
                
                // Fill the card HTML
                card.innerHTML = `
                    <div class="flex justify-between items-start gap-4">
                        <h3 class="text-white text-lg font-bold flex-1 leading-snug">${paper.title}</h3>
                        <div class="flex flex-col items-end shrink-0">
                            <span class="text-primary font-bold text-lg flex items-center gap-1">
                                <span class="material-symbols-outlined text-sm">format_quote</span>
                                ${paper.citationCount}
                            </span>
                            <span class="text-white/40 text-[10px] uppercase tracking-wider">Citations</span>
                        </div>
                    </div>
                    
                    <p class="text-white/60 text-sm italic mb-2">Authors: ${paper.authors.join(', ')}</p>
                    
                    <div class="relative">
                        <p id="abstract-${index}" class="text-white/80 text-sm leading-relaxed line-clamp-3 transition-all duration-300">
                            ${paper.abstract}
                        </p>
                        <button id="toggle-abstract-${index}" class="text-primary text-xs font-bold hover:underline mt-1 focus:outline-none">Read More</button>
                    </div>
                    
                    <div class="flex items-center justify-between mt-4 border-t border-white/10 pt-4">
                        <div class="flex gap-4">
                            <span class="text-white/50 text-xs flex items-center gap-1"><span class="material-symbols-outlined text-[14px]">calendar_today</span> ${year}</span>
                            <span class="text-white/50 text-xs flex items-center gap-1"><span class="material-symbols-outlined text-[14px]">link</span> arXiv:${paper.arxivId}</span>
                        </div>
                        
                        <button class="import-btn flex items-center justify-center gap-2 h-[36px] px-4 rounded-lg bg-primary/20 border border-primary/50 text-primary text-sm font-bold hover:bg-primary hover:text-background-dark transition-colors shadow-md" data-id="${paper.arxivId}">
                            <span class="material-symbols-outlined text-[18px]">download</span> Import to Library
                        </button>
                    </div>
                `;

                container.appendChild(card);
                
                // Add event listener for the "Read More" button
                const toggleBtn = document.getElementById(`toggle-abstract-${index}`);
                const abstractP = document.getElementById(`abstract-${index}`);
                
                toggleBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    if (abstractP.classList.contains('line-clamp-3')) {
                        abstractP.classList.remove('line-clamp-3');
                        toggleBtn.textContent = 'Read Less';
                    } else {
                        abstractP.classList.add('line-clamp-3');
                        toggleBtn.textContent = 'Read More';
                    }
                });
            });

            // Wire up the "Import to Library" buttons
            const importBtns = container.querySelectorAll('.import-btn');
            importBtns.forEach(btn => {
                btn.addEventListener('click', async (e) => {
                    // Prevent the click from triggering anything else
                    e.stopPropagation(); 
                    
                    const arxivId = btn.getAttribute('data-id');
                    
                    // Show loading state on the button
                    const originalHtml = btn.innerHTML;
                    btn.innerHTML = '<span class="material-symbols-outlined text-[18px] animate-spin">refresh</span> Importing...';
                    btn.disabled = true;
                    
                    // Trigger the import logic we already wrote in arxiv.js!
                    try {
                        const response = await fetch(`http://localhost:3000/api/arxiv/import`, {
                            method: 'POST',
                            headers: { 
                                'Authorization': `Bearer ${auth.getToken()}`,
                                'Content-Type': 'application/json'
                            },
                            body: JSON.stringify({ arxivId: arxivId })
                        });
                        const data = await response.json();

                        if (!response.ok) {
                            alert(data.message || 'Failed to import paper.');
                            btn.innerHTML = originalHtml;
                            btn.disabled = false;
                            return;
                        }

                        // Success state!
                        btn.innerHTML = '<span class="material-symbols-outlined text-[18px]">check</span> Imported';
                        btn.classList.remove('bg-primary/20', 'text-primary');
                        btn.classList.add('bg-green-500/20', 'text-green-500', 'border-green-500/50');
                        
                    } catch (error) {
                        console.error('Import error:', error);
                        alert('Network error while importing.');
                        btn.innerHTML = originalHtml;
                        btn.disabled = false;
                    }
                });
            });

        } catch (error) {
            console.error('Error performing search:', error);
            container.innerHTML = `<p class="text-red-400">A network error occurred.</p>`;
            countElement.textContent = 'Search failed.';
        }
    }
};
