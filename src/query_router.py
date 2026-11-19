from typing import Literal
from langchain_core.messages import HumanMessage, SystemMessage
from src.config import get_groq_llm

RouteType = Literal["SQL_ANALYTICS", "DOC_RAG", "HYBRID"]
VALID_ROUTES = {"SQL_ANALYTICS", "DOC_RAG", "HYBRID"}


def route_query(user_question: str) -> RouteType:
    """Classify a prompt into SQL_ANALYTICS, DOC_RAG, or HYBRID."""
    cleaned = user_question.strip()
    if not cleaned:
        return "HYBRID"

    llm = get_groq_llm(temperature=0.0)
    system_prompt = (
        "Classify the user's question into one of these exact labels:\n"
        "- SQL_ANALYTICS: Live stock prices, changes, volumes, comparisons, "
        "or aggregations from SQL tables.\n"
        "- DOC_RAG: Qualitative commentary, strategy, risk factors, or "
        "notes from uploaded PDFs.\n"
        "- HYBRID: Needs both SQL market/financial rows and uploaded "
        "PDF context.\n"
        "Respond ONLY with the label."
    )
    response = llm.invoke(
        [
            SystemMessage(content=system_prompt),
            HumanMessage(content=cleaned),
        ]
    )
    label = (
        response.content.strip().upper()
        if isinstance(response.content, str)
        else str(response.content).strip().upper()
    )
    if label in VALID_ROUTES:
        return label  # type: ignore[return-value]
    return "HYBRID"
