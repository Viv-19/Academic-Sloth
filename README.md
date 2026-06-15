# Academic Sloth 🦥

Academic Sloth is a comprehensive, AI-powered research assistant platform designed to help students, researchers, and academics seamlessly discover, read, and analyze academic papers. It features a custom **Agentic RAG (Retrieval-Augmented Generation)** pipeline that acts as an intelligent research partner.

## 🚀 Features
- **Paper Library Management**: Upload your own PDF papers or search and fetch directly from arXiv.
- **Agentic AI Chat**: Ask highly specific or broad questions about a paper. The LangGraph-powered AI backend uses 5 specialized agents (Summary, Factual, Deep Dive, Compare, Critique) to properly analyze the document.
- **Live "Thinking" Stream**: Real-time progress updates directly in the chat UI so you know exactly what the AI is doing.
- **Grounding Guard**: Ensures the AI doesn't hallucinate. It mathematically verifies that the generated claims match the original source text.
- **Citation Engine**: Provides clickable citations back to the exact page of the PDF where the answer was found.

---

## 🏗️ Architecture Stack

The project is split into three main components:

### 1. `Sloth_frontend` (Vanilla HTML/JS/CSS)
A lightweight, fast, and highly interactive user interface powered by TailwindCSS. It connects securely to the Node.js backend.

### 2. `Sloth_backend` (Node.js & Express)
The primary API gateway. It handles user authentication (JWT), email OTP verification, database interactions (Prisma/PostgreSQL), and serves the frontend static files. It also proxies all AI-related chat requests over to the Python service.

### 3. `Sloth_ai_service` (Python & FastAPI)
The brain of the platform. This microservice uses LangChain and LangGraph to orchestrate complex RAG workflows, manage conversational memory, index documents into ChromaDB (Vector Database), and interface with LLMs (Groq).

---

## 💻 How to Run Locally

To get the full application running, you need to start **both** the Node.js backend and the Python AI service. (The Node.js backend automatically serves the frontend).

### Step 1: Database Setup
1. Ensure you have **PostgreSQL** installed and running on your machine.
2. Open `Sloth_backend/.env` and verify the `DATABASE_URL` matches your local postgres credentials (username, password, and port).
3. Open a terminal and run the database migrations to build your tables:
```bash
cd Sloth_backend
npm install
npx prisma db push
```

### Step 2: Start the Node.js Backend
This server will handle logins, file uploads, and host the UI on `localhost:3000`.
```bash
cd Sloth_backend
npm run dev 
# (Or node src/server.js)
```

### Step 3: Start the Python AI Service
This microservice must run simultaneously on `localhost:8000` to process the document indexing and chat queries.
1. Open a new terminal window.
2. Ensure you have added your API keys (like `GROQ_API_KEY`) to `Sloth_ai_service/.env`.
```bash
cd Sloth_ai_service
# Install dependencies
pip install -r requirements.txt

# Start the server (with auto-reload enabled)
uvicorn app.main:app --reload --port 8000
```

### Step 4: Access the App
Once both servers are running successfully, open your web browser and go to:
👉 **[http://localhost:3000](http://localhost:3000)**

You can sign up for a new account, upload a paper, and start chatting with the AI!
