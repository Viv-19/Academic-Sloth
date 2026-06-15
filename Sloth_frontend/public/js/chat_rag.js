/**
 * js/chat_rag.js — Frontend SSE Chat Client
 * ==========================================
 * Handles real-time streaming chat with the RAG backend.
 *
 * EVENT TYPES from the Python backend:
 *   token         → A single text token to append to the current bubble
 *   done          → Streaming complete; carries source page numbers
 *   needs_indexing→ Paper not indexed yet; auto-triggers ingestion + shows progress
 *   error         → Fatal error; displays message to user
 */

const AI_CHAT_URL = 'http://localhost:3000/api/ai/chat';
const AI_INGEST_URL = 'http://localhost:3000/api/ai/ingest';

export const ragChat = {

    /**
     * Triggers document ingestion via the Node.js backend.
     * Returns true on success, false on failure.
     */
    async triggerIngestion(docId, token) {
        try {
            const res = await fetch(`${AI_INGEST_URL}/${docId}`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` },
            });
            if (!res.ok) {
                console.warn(`[RAG] Ingest request failed: ${res.status}`);
                return false;
            }
            const data = await res.json();
            console.log('[RAG] Ingestion triggered:', data.message);
            return true;
        } catch (e) {
            console.warn('[RAG] Ingestion trigger failed:', e.message);
            return false;
        }
    },

    /**
     * Sends a question and streams the response into the chat UI.
     */
    async sendMessage(docId, question, token, messagesEl) {
        if (!question.trim()) return;

        this._appendUserMessage(question, messagesEl);
        const { bubble, textNode } = this._createAiBubble(messagesEl);
        let fullResponse = '';

        try {
            const response = await fetch(AI_CHAT_URL, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`,
                },
                body: JSON.stringify({ doc_id: docId, question }),
            });

            if (!response.ok) {
                textNode.textContent = '❌ Failed to reach the AI service. Make sure the Python server is running on port 8000.';
                return;
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n\n');
                buffer = lines.pop(); // Keep incomplete last chunk

                for (const line of lines) {
                    if (!line.startsWith('data: ')) continue;

                    try {
                        const event = JSON.parse(line.slice(6));

                        if (event.type === 'token') {
                            // When the first token arrives, remove the agent steps UI
                            const stepList = bubble.querySelector('.agent-steps');
                            if (stepList) stepList.remove();
                            
                            fullResponse += event.content;
                            textNode.textContent = this._cleanResponseText(fullResponse);
                            messagesEl.scrollTop = messagesEl.scrollHeight;

                        } else if (event.type === 'agent_step') {
                            // Check if steps container exists, otherwise create it
                            let stepList = bubble.querySelector('.agent-steps');
                            if (!stepList) {
                                stepList = document.createElement('div');
                                stepList.className = 'agent-steps flex flex-col gap-2 mb-2 pb-2 border-b border-white/10';
                                bubble.insertBefore(stepList, textNode);
                                textNode.textContent = ''; // Clear the initial placeholder
                            }

                            const stepItem = document.createElement('div');
                            stepItem.className = 'flex items-center gap-2 text-primary/80 text-xs font-medium animate-pulse';
                            stepItem.innerHTML = `<span class="material-symbols-outlined text-[14px]">psychology</span> ${event.content}`;
                            stepList.appendChild(stepItem);
                            messagesEl.scrollTop = messagesEl.scrollHeight;

                        } else if (event.type === 'done') {
                            if (event.sources && event.sources.length > 0) {
                                this._renderSources(event.sources, bubble, messagesEl);
                            }

                        } else if (event.type === 'needs_indexing') {
                            // ── Auto-recover: trigger indexing and show progress ──────────
                            // The paper wasn't indexed. We auto-trigger ingestion and
                            // replace the bubble with an animated progress indicator.
                            // The user can ask again once indexing completes (~60s).
                            this._renderIndexingProgress(bubble, textNode, docId, token, question, messagesEl);

                        } else if (event.type === 'error') {
                            textNode.textContent = `❌ ${event.content}`;
                        }

                    } catch (parseErr) {
                        console.warn('[RAG] Could not parse SSE event:', line);
                    }
                }
            }

        } catch (err) {
            console.error('[RAG] Stream error:', err);
            textNode.textContent = '❌ Connection error. Is the Python service running on port 8000?';
        }
    },

    // ─── Indexing Progress UI ──────────────────────────────────────────────

    async _renderIndexingProgress(bubble, textNode, docId, token, originalQuestion, messagesEl) {
        // Step 1: Trigger the actual ingestion
        const triggered = await this.triggerIngestion(docId, token);

        if (!triggered) {
            textNode.textContent = '❌ Could not start indexing. Check that both servers are running.';
            return;
        }

        // Step 2: Show animated progress UI
        bubble.innerHTML = `
            <div class="flex items-center gap-3 mb-3">
                <div class="size-2 rounded-full bg-amber-400 animate-pulse"></div>
                <span class="text-amber-400 text-sm font-medium">Indexing paper...</span>
            </div>
            <div class="w-full bg-white/5 rounded-full h-1.5 overflow-hidden mb-3">
                <div id="index-progress-bar" class="h-full bg-gradient-to-r from-amber-500 to-orange-400 rounded-full transition-all duration-1000" style="width: 0%"></div>
            </div>
            <p class="text-white/50 text-xs leading-relaxed">
                Extracting text, creating chunks, and generating embeddings.<br>
                <span id="index-status-text">This usually takes 30–90 seconds...</span>
            </p>
            <button id="retry-chat-btn" class="mt-3 hidden px-3 py-1.5 rounded-lg bg-primary/20 border border-primary/30 text-primary text-xs font-medium hover:bg-primary/30 transition-colors">
                ✓ Ask my question now
            </button>
        `;
        messagesEl.scrollTop = messagesEl.scrollHeight;

        // Step 3: Animate the progress bar over ~75 seconds (estimated indexing time)
        const progressBar = document.getElementById('index-progress-bar');
        const statusText = document.getElementById('index-status-text');
        const retryBtn = document.getElementById('retry-chat-btn');

        const stages = [
            { pct: 15, label: 'Extracting text from PDF...', delay: 2000 },
            { pct: 35, label: 'Splitting into semantic chunks...', delay: 8000 },
            { pct: 60, label: 'Generating embeddings (local model)...', delay: 20000 },
            { pct: 85, label: 'Storing vectors in ChromaDB...', delay: 40000 },
            { pct: 95, label: 'Almost done...', delay: 60000 },
        ];

        for (const stage of stages) {
            await new Promise(r => setTimeout(r, stage.delay));
            if (progressBar) progressBar.style.width = `${stage.pct}%`;
            if (statusText) statusText.textContent = stage.label;
        }

        // Step 4: After estimated time, show the retry button
        if (progressBar) progressBar.style.width = '100%';
        if (statusText) statusText.textContent = '✅ Indexing should be complete! Click below to ask your question.';

        if (retryBtn) {
            retryBtn.classList.remove('hidden');
            retryBtn.addEventListener('click', async () => {
                bubble.remove(); // Remove the progress bubble
                await this.sendMessage(docId, originalQuestion, token, messagesEl);
            });
        }
    },

    // ─── UI Helpers ────────────────────────────────────────────────────────

    _appendUserMessage(text, container) {
        const wrapper = document.createElement('div');
        wrapper.className = 'flex justify-end';
        wrapper.innerHTML = `
            <div class="bg-primary/20 border border-primary/30 rounded-2xl rounded-tr-sm px-4 py-2.5 text-sm text-white max-w-[85%] leading-relaxed">
                ${this._escapeHtml(text)}
            </div>
        `;
        container.appendChild(wrapper);
        container.scrollTop = container.scrollHeight;
    },

    _createAiBubble(container) {
        const wrapper = document.createElement('div');
        wrapper.className = 'flex gap-3 items-start';

        const textNode = document.createTextNode('▌');

        wrapper.innerHTML = `
            <div class="size-8 rounded-full bg-primary/20 text-primary flex items-center justify-center shrink-0 border border-primary/30">
                <span class="material-symbols-outlined text-[16px]">auto_awesome</span>
            </div>
        `;
        const bubble = document.createElement('div');
        bubble.className = 'bg-white/5 border border-white/10 rounded-2xl rounded-tl-sm p-3 text-sm text-white/90 leading-relaxed max-w-[85%]';
        bubble.appendChild(textNode);
        wrapper.appendChild(bubble);
        container.appendChild(wrapper);
        container.scrollTop = container.scrollHeight;

        return { bubble, textNode };
    },

    _renderSources(sources, bubble, container) {
        const pages = [...new Set(sources.map(s => s.page))].sort((a, b) => a - b);
        if (!pages.length) return;

        const sourcesEl = document.createElement('div');
        sourcesEl.className = 'flex flex-wrap gap-1.5 mt-3 pt-3 border-t border-white/10';
        sourcesEl.innerHTML = `<span class="text-white/40 text-[10px] w-full font-semibold uppercase tracking-widest">Sources</span>`;

        pages.forEach(page => {
            const pill = document.createElement('button');
            pill.className = 'px-2.5 py-1 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-400 text-[10px] font-medium hover:bg-blue-500/20 transition-colors';
            pill.textContent = `Page ${page}`;
            pill.addEventListener('click', () => {
                const iframe = document.querySelector('#paper-content iframe');
                if (iframe) {
                    const baseUrl = iframe.src.split('#')[0];
                    iframe.src = `${baseUrl}#page=${page}`;
                }
            });
            sourcesEl.appendChild(pill);
        });

        bubble.appendChild(sourcesEl);
        container.scrollTop = container.scrollHeight;
    },

    _cleanResponseText(text) {
        return text.replace(/```json[\s\S]*?```/g, '').trim();
    },

    _escapeHtml(text) {
        return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    },
};
