# Engineering Challenges & Solutions

Building a production-grade Retrieval-Augmented Generation (RAG) application introduces several unique architectural and stability challenges. Below are the core hurdles encountered during development and how they were resolved.

## 1. Cloud API Rate Limiting (The "429" Problem)
**Challenge**: Relying on the Groq free tier for high-speed LLM inference resulted in frequent HTTP `429 Too Many Requests` errors, especially during extensive paper analysis or rapid chat interactions.

**Solution**:
Implemented the `GroqRotatingClient` architecture. The system is configured with a pool of 8 API keys. When a rate limit is hit, the client performs a round-robin rotation, instantly retrying the request with the next key. If all keys are exhausted on the primary high-capacity model (Llama 70B), the system automatically falls back to a smaller, faster model (Llama 8B) as a circuit breaker, ensuring graceful degradation rather than system failure.

## 2. Asynchronous Ingestion & UI State Sync
**Challenge**: RAG ingestion (chunking and embedding a 30-page PDF) takes time. In early iterations, the user could navigate to the chat interface before the document was indexed, resulting in a blank response or a system crash.

**Solution**:
Transitioned to an event-driven architecture. The ingestion endpoint was modified to immediately return a `202 Accepted` status while processing in a background thread. If the frontend queries the chat endpoint for an unindexed paper, the Python service emits a special `needs_indexing` Server-Sent Event (SSE). The frontend intercepts this event, displays an automated "Indexing in progress" UI animation, and automatically triggers the background ingestion, bridging the gap seamlessly.

## 3. High Latency & Cost of Cloud Embeddings
**Challenge**: Using cloud-based providers (like Google or OpenAI) for embeddings incurred network latency for every chunk and ran the risk of incurring high costs at scale.

**Solution**:
Migrated entirely to a local execution model for embeddings. By utilizing `sentence-transformers` and the `BAAI/bge-small-en-v1.5` model, the application now generates high-quality 384-dimensional vectors directly on the host CPU. This reduced network latency to zero, eliminated rate limits entirely, and brought embedding costs to $0.

## 4. RAG Retrieval Accuracy
**Challenge**: Standard bi-encoder vector similarity (cosine distance) often returned text chunks that were topically related but didn't actually contain the answer to the specific user query.

**Solution**:
Implemented a **Dual-Stage Retrieval Pipeline**. 
1. The bi-encoder rapidly retrieves an over-sampled candidate pool (Top 15 chunks).
2. A local MS MARCO cross-encoder model then re-ranks these pairs (Question + Chunk), assessing the deep logical relevance of the text to the prompt.
This approach significantly reduced LLM hallucinations and improved the precision of academic source citations.

## 5. File Descriptor Leaks & Corrupt PDFs
**Challenge**: During the PDF extraction phase, the system would occasionally crash with a `ValueError: document closed` exception when attempting to access metadata after closing the PyMuPDF document handle.

**Solution**:
Refactored the `pdf_extractor.py` service to rigorously enforce order-of-operations. Metadata (like total page count) is now explicitly cached in memory before the document handle is safely closed using `try/finally` blocks, ensuring robust memory management and preventing pipeline failures.
