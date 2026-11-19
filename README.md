# Enterprise SQL & Financial Document RAG Copilot

An AI-powered financial analytics and document intelligence copilot built with **FastAPI**, **Streamlit**, **Microsoft SQL Server (`pyodbc`)**, **FAISS**, **Groq (`llama-3.3-70b-versatile`)**, and **`sqlglot`**. It syncs live equity market snapshots into SQL Server, routes user queries across `SQL_ANALYTICS`, `DOC_RAG`, and `HYBRID` modes, enforces read-only SQL AST guardrails, and returns grounded answers with source citations.

## Architecture & Key Features

- **Query Routing (`SQL_ANALYTICS` / `DOC_RAG` / `HYBRID`):** Classifies incoming questions to query structured SQL Server tables, retrieve indexed financial PDF chunks from FAISS, or combine both for cross-source comparisons.
- **Live Market Data Sync (`yfinance` -> SQL Server):** Fetches real-time equity market data (`RELIANCE.NS`, `TCS.NS`, `INFY.NS`, `AAPL`, `MSFT`) and upserts snapshots into `dbo.live_market_snapshots` inside the `enterprise_finance` database.
- **Read-Only SQL AST Guardrail (`sqlglot`):** Parses generated T-SQL statements into an AST to enforce single-statement execution and block destructive mutations (`DELETE`, `DROP`, `UPDATE`, `INSERT`, `ALTER`, `TRUNCATE`).
- **Financial PDF RAG (`pypdf` + FAISS):** Extracts text from uploaded financial reports, splits into overlapping chunks, embeds vectors, persists the FAISS index locally, and surfaces page-level citations.
- **Interactive Copilot UI (Streamlit + FastAPI):** Provides one-click market sync, PDF ingestion, route badges, generated SQL inspection, live table previews, and citation panels.

## Tech Stack

- **Backend API:** FastAPI, Uvicorn, Pydantic
- **Frontend UI:** Streamlit
- **Database & ORM:** Microsoft SQL Server (`localhost\MMSSQL`), `pyodbc`, SQLAlchemy, `sqlglot`
- **Market Data & RAG:** `yfinance`, `pypdf`, FAISS, HuggingFace Embeddings
- **LLM Inference:** Groq API (`llama-3.3-70b-versatile`)

## Project Structure

```text
enterprise-sql-rag-copilot/
├── api/
│   └── main.py              # FastAPI endpoints (health, sync, query, ingest-pdf)
├── src/
│   ├── config.py            # Environment settings and SQL Server URI builder
│   ├── sql_guard.py         # sqlglot AST validator for read-only T-SQL
│   └── rag_engine.py        # PDF ingestion, FAISS indexing, and retrieval
├── ui/
│   └── app.py               # Streamlit copilot interface
├── tests/
│   └── test_sql_guard.py    # Unit tests for SQL guardrails and market logic
├── .env.example             # Environment variable template (no secrets)
├── .gitignore               # Ignores .env, venv/, FAISS index, and PDFs
├── requirements.txt         # Python dependencies
└── README.md
```

## Environment Setup

1. **Clone and enter the project directory:**

   ```cmd
   git clone [https://github.com/bhaddrimahesh7/enterprise-sql-rag-copilot.git](https://github.com/bhaddrimahesh7/enterprise-sql-rag-copilot.git)
   cd enterprise-sql-rag-copilot
   ```

2. **Create and activate a virtual environment:**

   ```cmd
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure environment variables:**
   Copy `.env.example` to `.env` and set your local SQL Server instance and Groq key:
   ```cmd
   copy .env.example .env
   notepad .env
   ```
   Example `.env` keys:
   ```env
   GROQ_API_KEY=your_groq_api_key
   GROQ_MODEL_NAME=llama-3.3-70b-versatile
   MSSQL_SERVER=localhost\MMSSQL
   MSSQL_DATABASE=enterprise_finance
   MSSQL_DRIVER=ODBC Driver 17 for SQL Server
   MSSQL_TRUSTED_CONNECTION=yes
   ```

## Running the Application

1. **Run unit tests:**

   ```cmd
   python -m pytest -v
   ```

2. **Start the FastAPI backend (Terminal 1):**

   ```cmd
   python -m uvicorn api.main:app --reload --port 8000
   ```

3. **Start the Streamlit frontend (Terminal 2):**

   ```cmd
   venv\Scripts\activate
   python -m streamlit run ui/app.py
   ```

4. Open `http://localhost:8501`, click **Sync Live Market Data**, upload a financial PDF in the sidebar and click **Index PDF**, then test `SQL_ANALYTICS`, `DOC_RAG`, and `HYBRID` prompts.
