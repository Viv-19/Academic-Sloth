# Technology Stack

Academic Sloth relies on a modern, robust technology stack optimized for high-performance AI integration, structured data management, and rapid frontend delivery.

## 1. Frontend
- **HTML5 & CSS3**: Semantic markup and modern styling.
- **Vanilla JavaScript (ES6+)**: Core logic, DOM manipulation, and asynchronous network requests (Fetch API, Server-Sent Events).
- **TailwindCSS**: Utility-first CSS framework via CDN for rapid, responsive UI development.
- **Material Symbols**: Google's modern icon library.

## 2. Backend (Node.js)
- **Node.js**: Asynchronous, event-driven JavaScript runtime.
- **Express.js**: Fast, unopinionated web framework for building RESTful APIs.
- **Prisma ORM**: Next-generation Node.js and TypeScript ORM used for type-safe database access and migrations.
- **PostgreSQL**: Robust, open-source relational database for storing users, document metadata, and application state.
- **JWT (JSON Web Tokens)**: Stateless, secure user authentication.
- **Bcrypt.js**: Cryptographic password hashing.
- **Multer**: Middleware for handling `multipart/form-data` and PDF file uploads.
- **Nodemailer**: Email sending service for OTP verification and password resets.
- **Helmet & CORS**: Security middleware for HTTP headers and cross-origin resource sharing.

## 3. AI Service (Python)
- **Python 3.10+**: Core language for data science and AI scripting.
- **FastAPI**: Modern, fast web framework for building APIs with Python, utilized for its asynchronous capabilities (`async/await`).
- **Uvicorn**: Lightning-fast ASGI server implementation.
- **PyMuPDF (fitz)**: High-performance PDF parsing and text extraction.
- **Sentence-Transformers**: Local, CPU-efficient library for generating embeddings and running cross-encoders without external API dependencies.
  - *Embedding Model*: `BAAI/bge-small-en-v1.5` (384-dimensional).
  - *Re-ranking Model*: `cross-encoder/ms-marco-MiniLM-L-6-v2`.
- **ChromaDB**: Open-source, local vector database for storing embeddings and performing semantic similarity searches.
- **Groq SDK**: High-speed LLM inference engine.
  - *Primary Model*: `llama-3.3-70b-versatile`.
  - *Fallback Model*: `llama-3.1-8b-instant`.
- **Pydantic**: Data validation and settings management using Python type annotations.
