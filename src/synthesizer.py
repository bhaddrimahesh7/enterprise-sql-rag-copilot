import json
from typing import Any, Dict, List, Optional
from langchain_core.messages import HumanMessage, SystemMessage
from src.config import get_groq_llm


def synthesize_answer(
    question: str,
    route: str,
    sql_query: Optional[str],
    sql_rows: List[Dict[str, Any]],
    doc_citations: List[Dict[str, Any]],
) -> str:
    """Generate a grounded answer strictly from SQL rows and PDF chunks."""
    llm = get_groq_llm(temperature=0.1)
    payload = {
        "route": route,
        "executed_sql": sql_query,
        "sql_rows": sql_rows,
        "document_citations": doc_citations,
    }
    system_prompt = (
        "Answer the user's question using ONLY the provided sql_rows and "
        "document_citations.\n"
        "- Include currency codes/symbols and sync timestamps from SQL rows "
        "when relevant.\n"
        "- Cite PDF passages with filename and page number, e.g. "
        "(annual_report.pdf, p. 4).\n"
        "- If both sql_rows and document_citations are empty, state clearly "
        "that no matching records or indexed PDF chunks were found without "
        "guessing."
    )
    user_prompt = (
        f"Question: {question}\n\n"
        f"Context:\n{json.dumps(payload, default=str, indent=2)}"
    )
    response = llm.invoke(
        [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]
    )
    return (
        response.content.strip()
        if isinstance(response.content, str)
        else str(response.content).strip()
    )
