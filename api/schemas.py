from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SyncRequest(BaseModel):
    tickers: Optional[List[str]] = None


class SyncResponse(BaseModel):
    synced_count: int
    failed_tickers: List[str]
    synced_at_utc: str


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=1000)
    top_k: int = Field(default=4, ge=1, le=10)


class CitationItem(BaseModel):
    source: str
    page: int
    content: str


class QueryResponse(BaseModel):
    route: str
    answer: str
    executed_sql: Optional[str] = None
    sql_rows: List[Dict[str, Any]] = Field(default_factory=list)
    citations: List[CitationItem] = Field(default_factory=list)


class IngestResponse(BaseModel):
    filename: str
    chunks_indexed: int
    status: str
