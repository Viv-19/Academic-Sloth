# 🎓 Academic Sloth — AI Research Assistant

Academic Sloth is a production-grade RAG (Retrieval-Augmented Generation) pipeline designed to ingest, process, and analyze academic papers. It features a high-performance Python AI service, a robust Node.js backend, and a modern web frontend.

---

## 🏗️ System Architecture

- **`Sloth_frontend/`**: Static HTML/JS frontend with glassmorphism UI.
- **`Sloth_backend/`**: Node.js (Express) server handling users, file uploads, and logic orchestration.
- **`Sloth_ai_service/`**: Python (FastAPI) engine for PDF processing, embedding, and LLM chat (RAG).
- **`database`**: PostgreSQL (via Prisma ORM).
- **`vector_db`**: ChromaDB (Local vector storage).

---

## 🛠️ Prerequisites

Before you begin, ensure you have the following installed:
- **Node.js** (v18+)
- **Python** (v3.10+)
- **PostgreSQL** (Running locally or on a server)
- **Groq API Key** (Get one for free at [console.groq.com](https://console.groq.com))

---

## 🚀 Setup & Installation

### 1. Database Setup
Create a PostgreSQL database named `researchos`.

### 2. Environment Configuration
Create a `.env` file in the **root** directory (for Node.js) and in `Sloth_ai_service/` (for Python).

**Root `.env` (Node.js):**
```env
DATABASE_URL="postgresql://user:password@localhost:5432/researchos?schema=public"
JWT_SECRET="your_secure_secret_here"
EMAIL_USER="your-email@gmail.com"
EMAIL_PASS="your-app-password"
```

**`Sloth_ai_service/.env` (Python):**
```env
GROQ_API_KEYS="gsk_your_key_1,gsk_your_key_2"
GROQ_PRIMARY_MODEL="llama-3.3-70b-versatile"
EMBEDDING_MODEL="BAAI/bge-small-en-v1.5"
BACKEND_URL="http://localhost:3000"
```

### 3. Backend & Frontend Setup (Node.js)
In the root directory:
```powershell
# Install dependencies
npm install

# Run database migrations
npx prisma migrate dev --name init

# Start the backend server
npm run dev
```
*The backend will run on `http://localhost:3000`.*

### 4. AI Service Setup (Python)
In the `Sloth_ai_service/` directory:
```powershell
# Create a virtual environment
python -m venv venv
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start the AI service
uvicorn app.main:app --reload --port 8000
```
*The AI service will run on `http://localhost:8000`.*

---

## 📖 Usage

1. **Start the Backend**: Run `npm run dev` in the root.
2. **Start the AI Service**: Run `uvicorn` in the `Sloth_ai_service` folder.
3. **Open the Frontend**: Use a static server (like VS Code Live Server) to open `Sloth_frontend/public/landing_page.html`.
4. **Upload a Paper**: Sign up/Sign in, go to the library, and upload a PDF.
5. **Chat with AI**: Once ingested, use the Chat interface to ask questions about the paper.

---

## 🧪 Testing

- **Backend Health Check**: `http://localhost:3000/health`
- **AI Service Docs (Swagger)**: `http://localhost:8000/docs`
- **AI Service Health**: `http://localhost:8000/api/health`

---

## 📝 Project Notes
- The AI service uses **Groq** for fast inference and **sentence-transformers** for local CPU embeddings.
- Vector data is stored locally in `Sloth_ai_service/data/chroma_db`.
- PDF processing is handled by **PyMuPDF**.
