import os
import shutil
from typing import Any, Dict, Optional, cast
from fastapi import FastAPI, File, HTTPException, UploadFile
from api.schemas import (
    IngestResponse,
    QueryRequest,
    QueryResponse,
    SyncRequest,
    SyncResponse,
)
from src.live_sync import LiveMarketSyncService
from src.query_router import route_query
from src.rag_engine import FinancialDocumentRAG
from src.sql_engine import SQLServerTextToSQLEngine, UnsafeSQLError
from src.synthesizer import synthesize_answer

app = FastAPI(
    title="Live SQL Server & Financial Document RAG Copilot",
    version="1.2.0",
)

sync_service = LiveMarketSyncService()
sql_engine = SQLServerTextToSQLEngine(engine=sync_service.engine)
rag_engine = FinancialDocumentRAG()


@app.get("/health")
def health_check() -> Dict[str, Optional[str]]:
    try:
        last_sync = sync_service.get_latest_sync_time()
    except Exception:
        last_sync = None
    return {"status": "ok", "last_live_sync_utc": last_sync}


@app.post("/sync-live", response_model=SyncResponse)
def sync_live_market(payload: Optional[SyncRequest] = None) -> SyncResponse:
    try:
        tickers = payload.tickers if payload else None
        result: Dict[str, Any] = sync_service.sync_tickers(tickers=tickers)
        return SyncResponse(**result)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Live sync failed: {exc}"
        ) from exc


@app.post("/ingest-pdf", response_model=IngestResponse)
def ingest_pdf(file: UploadFile = File(...)) -> IngestResponse:
    safe_name = os.path.basename(file.filename or "")
    if not safe_name.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only .pdf files are supported.",
        )

    os.makedirs("data/raw_pdfs", exist_ok=True)
    save_path = os.path.join("data/raw_pdfs", safe_name)

    try:
        with open(save_path, "wb") as out_file:
            shutil.copyfileobj(file.file, out_file)
        chunks_count = rag_engine.ingest_pdf(save_path)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"PDF ingestion failed: {exc}"
        ) from exc
    finally:
        file.file.close()

    return IngestResponse(
        filename=safe_name,
        chunks_indexed=chunks_count,
        status="indexed",
    )


@app.post("/ask", response_model=QueryResponse)
def ask_copilot(payload: QueryRequest) -> QueryResponse:
    try:
        route = route_query(payload.question)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Routing failed: {exc}",
        ) from exc

    executed_sql = None
    sql_rows = []
    citations = []

    if route in ("SQL_ANALYTICS", "HYBRID"):
        try:
            executed_sql, sql_rows = sql_engine.execute_question(
                payload.question
            )
        except UnsafeSQLError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"SQL query failed: {exc}",
            ) from exc

    if route in ("DOC_RAG", "HYBRID"):
        try:
            citations = rag_engine.retrieve(
                payload.question, top_k=payload.top_k
            )
        except Exception as exc:
            raise HTTPException(
                status_code=500, detail=f"RAG retrieval failed: {exc}"
            ) from exc

    try:
        answer = synthesize_answer(
            question=payload.question,
            route=route,
            sql_query=executed_sql,
            sql_rows=sql_rows,
            doc_citations=citations,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Synthesis failed: {exc}"
        ) from exc

    return QueryResponse(
        route=route,
        answer=answer,
        executed_sql=executed_sql,
        sql_rows=sql_rows,
        citations=cast(Any, citations),
    )
