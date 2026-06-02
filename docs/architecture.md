# Academic Sloth Architecture

Academic Sloth uses a decoupled, microservices-inspired architecture designed for performance, scalability, and separation of concerns. The system is split across three distinct layers: a single-page application (SPA) frontend, a Node.js Backend-for-Frontend (BFF), and a Python AI Service.

## System Components

### 1. Frontend (Client Layer)
The frontend is a lightweight Single-Page Application (SPA) built using Vanilla JavaScript and TailwindCSS.
- **Event-Driven UI**: Automatically triggers and listens for ingestion status events (`needs_indexing`), providing real-time feedback to the user without blocking interactions.
- **Streaming Interface**: Utilizes the `EventSource` API to consume Server-Sent Events (SSE) from the backend, rendering AI responses word-by-word.
- **Document Viewer**: Embeds an iframe for rendering PDFs natively in the browser, working alongside the AI chat pane for a split-view research experience.

### 2. Backend (Node.js / Express)
The Node.js server acts as the primary orchestrator and Backend-for-Frontend (BFF).
- **Authentication & Authorization**: Manages user accounts, OTP-based email verification, and issues JSON Web Tokens (JWT) for secure routing.
- **Database Management**: Uses Prisma ORM to interact with a PostgreSQL database, storing user metadata, document tracking, and chat histories.
- **Proxy Orchestration**: Safely proxies AI requests to the Python service. This keeps all Groq API keys and vector database logic hidden from the client, ensuring security.
- **File Management**: Uses Multer to handle PDF uploads, storing them securely before ingestion.

### 3. AI Service (Python / FastAPI)
The Python service handles all heavy lifting, machine learning, and retrieval-augmented generation (RAG) operations.
- **Idempotent Ingestion Pipeline**: Extracts text from PDFs using `PyMuPDF`, splits text into semantic chunks, and generates embeddings. The pipeline checks the vector store first to prevent redundant processing.
- **Local Embedding**: Uses `sentence-transformers` and the `BAAI/bge-small-en-v1.5` model to generate high-quality 384-dimensional vectors entirely on the CPU (zero API cost, low latency).
- **Vector Storage**: Integrates with ChromaDB for fast, persistent, local vector similarity search.
- **Dual-Stage RAG**:
  1. **Retrieval**: Bi-encoder similarity search grabs the top 15 candidate chunks.
  2. **Re-ranking**: An MS MARCO Cross-Encoder re-scores the pairs (question + chunk) to yield the top 5 most highly relevant excerpts.
- **Resilient LLM Generation**: Uses a custom `GroqRotatingClient` to distribute loads across multiple free-tier Groq API keys and falls back to faster/smaller models (Llama 8B) if the primary model (Llama 70B) hits a rate limit.

## Communication Flow

1. **Upload**: User uploads a PDF → Node.js saves metadata to PostgreSQL and physical file to disk. Node.js fires a background request to Python to begin ingestion.
2. **Ingestion**: Python extracts, chunks, embeds, and stores the document in ChromaDB. Once complete, it sends a webhook/callback back to Node.js to update the document's status to "indexed".
3. **Chat Request**: User asks a question → Request hits Node.js → Node.js verifies JWT and forwards to Python.
4. **Streaming Response**: Python performs RAG, connects to the Groq API, and streams the response back through Node.js to the frontend via SSE.
